# _*_ coding: utf-8 _*_
"""FHIRPath evaluator over :mod:`fhirpath.core.ast` trees."""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from . import ast
from .context import EvalContext, Environment
from .evaluation import EvaluationError
from .functions import FUNCTIONS, Call, Chain
from .model import Node
from .operators import arithmetic, comparison, equality
from .types import FPDate, FPDateTime, FPTime, Quantity, TypeInfo
from .values import (
    MISSING,
    is_type,
    resolve_type,
    singleton,
    singleton_boolean,
    singleton_value,
    system,
)

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

_MATH = ("*", "/", "div", "mod", "+", "-")
_LOGIC = ("and", "or", "xor", "implies")
_EQUALITY = ("=", "!=", "~", "!~")
_FHIR_CONSTANTS = {
    "ucum": "http://unitsofmeasure.org",
    "sct": "http://snomed.info/sct",
    "loinc": "http://loinc.org",
}


class Engine:
    """Evaluates AST nodes; stateless apart from the function registry."""

    def __init__(self, functions=None):
        self.functions = functions if functions is not None else FUNCTIONS

    # ------------------------------------------------------------------ entry
    def run(
        self,
        tree: ast.Node,
        resource: Any = None,
        variables: Optional[Dict[str, Any]] = None,
        env: Optional[Environment] = None,
    ) -> List[Any]:
        root = self.root_collection(resource)
        ctx = EvalContext(
            this=root,
            variables=self.initial_variables(root, variables),
            env=env or Environment(),
        )
        return self.evaluate(tree, ctx)

    @staticmethod
    def root_collection(resource: Any) -> List[Any]:
        if resource is None:
            return []
        if isinstance(resource, list):
            return [
                item if isinstance(item, Node) else Node.root(item) for item in resource
            ]
        if isinstance(resource, Node):
            return [resource]
        return [Node.root(resource)]

    @staticmethod
    def initial_variables(
        root: List[Any], variables: Optional[Dict[str, Any]]
    ) -> Dict[str, List[Any]]:
        values: Dict[str, List[Any]] = {"context": root}
        resource = [n.resource_node() or n for n in root if isinstance(n, Node)]
        values["resource"] = resource
        values["rootResource"] = [_root_resource(n) for n in resource]
        for name, constant in _FHIR_CONSTANTS.items():
            values[name] = [constant]
        for name, value in (variables or {}).items():
            if value is None:
                values[name] = []
            elif isinstance(value, list):
                values[name] = [_wrap(v) for v in value]
            else:
                values[name] = [_wrap(value)]
        return values

    # ------------------------------------------------------------- evaluation
    def evaluate(self, node: ast.Node, ctx: EvalContext) -> List[Any]:
        return self.chain(node, ctx)[0]

    def chain(self, node: ast.Node, ctx: EvalContext) -> Tuple[List[Any], EvalContext]:
        """Evaluate and return the context valid for the rest of an invocation chain."""
        if isinstance(node, ast.Invocation):
            left, ctx = self.chain(node.left, ctx)
            return self.invoke(node.right, left, ctx)
        if isinstance(node, (ast.Member, ast.Function, ast.This, ast.Index, ast.Total)):
            return self.invoke(node, ctx.this, ctx, term=True)
        method = self._dispatch.get(type(node))
        if method is None:
            raise EvaluationError(
                "unsupported expression node %s" % type(node).__name__
            )
        return method(self, node, ctx), ctx

    # ------------------------------------------------------------- invocation
    def invoke(
        self, node: ast.Node, input_: List[Any], ctx: EvalContext, term: bool = False
    ):
        if isinstance(node, ast.Member):
            return self.navigate(input_, node.name, term), ctx
        if isinstance(node, ast.Function):
            return self.call(node, input_, ctx)
        if isinstance(node, ast.This):
            return list(ctx.this), ctx
        if isinstance(node, ast.Index):
            return ([] if ctx.index is None else [ctx.index]), ctx
        if isinstance(node, ast.Total):
            return list(ctx.total or []), ctx
        raise EvaluationError("cannot invoke %s" % type(node).__name__)

    def navigate(self, items: List[Any], name: str, term: bool = False) -> List[Any]:
        result: List[Any] = []
        for item in items:
            if isinstance(item, Node):
                if term and not item.is_primitive and name in item.type_names():
                    result.append(item)
                    continue
                result.extend(item.child(name))
            elif isinstance(item, TypeInfo):
                value = (
                    getattr(item, name, None) if name in TypeInfo.__slots__ else None
                )
                if value is not None:
                    result.append(value)
            elif isinstance(item, Quantity):
                if name == "value":
                    result.append(item.value)
                elif name in ("unit", "code"):
                    result.append(item.unit)
        return result

    def call(self, node: ast.Function, input_: List[Any], ctx: EvalContext):
        spec = self.functions.get(node.name)
        if spec is None:
            raise EvaluationError("unknown function '%s'" % node.name, node.name)
        argc = len(node.args)
        if argc < spec.min_args or argc > spec.max_args:
            raise EvaluationError(
                "%s() expects %s argument(s), got %d"
                % (
                    node.name,
                    (
                        spec.min_args
                        if spec.min_args == spec.max_args
                        else "%d-%d" % (spec.min_args, spec.max_args)
                    ),
                    argc,
                ),
                node.name,
            )
        result = spec.impl(Call(self, ctx, input_, node.args, node.name))
        if isinstance(result, Chain):
            return result.result, result.ctx
        return result, ctx

    # -------------------------------------------------------------- terms
    def _literal(self, node: ast.Literal, ctx: EvalContext) -> List[Any]:
        return [] if node.value is None else [node.value]

    def _external(self, node: ast.ExternalConstant, ctx: EvalContext) -> List[Any]:
        name = node.name
        if name in ctx.variables:
            return list(ctx.variables[name])
        if name.startswith("vs-"):
            return ["http://hl7.org/fhir/ValueSet/" + name[3:]]
        if name.startswith("ext-"):
            return ["http://hl7.org/fhir/StructureDefinition/" + name[4:]]
        raise EvaluationError("undefined environment variable %%%s" % name, "%" + name)

    def _indexer(self, node: ast.Indexer, ctx: EvalContext) -> List[Any]:
        items = self.evaluate(node.left, ctx)
        index = singleton_value(self.evaluate(node.index, ctx), "index")
        if index is MISSING:
            return []
        if isinstance(index, bool) or not isinstance(index, int):
            raise EvaluationError("index must be an Integer")
        if 0 <= index < len(items):
            return [items[index]]
        return []

    def _unary(self, node: ast.Unary, ctx: EvalContext) -> List[Any]:
        value = singleton_value(
            self.evaluate(node.operand, ctx), "operand of unary %s" % node.op
        )
        if value is MISSING:
            return []
        if node.op == "-":
            result = arithmetic.negate(value)
        else:
            result = arithmetic.positive(value)
        return [] if result is None else [result]

    def _type_operation(self, node: ast.TypeOperation, ctx: EvalContext) -> List[Any]:
        items = self.evaluate(node.left, ctx)
        candidates = resolve_type(node.type_specifier)
        item = singleton(items, "left operand of '%s'" % node.op)
        if item is MISSING:
            return []
        if node.op == "is":
            return [is_type(item, candidates)]
        return [item] if is_type(item, candidates, exact=True) else []

    def _instance_selector(
        self, node: ast.InstanceSelector, ctx: EvalContext
    ) -> List[Any]:
        data: Dict[str, Any] = {}
        for name, expression in node.elements:
            values = [to_json(v) for v in self.evaluate(expression, ctx)]
            if not values:
                continue
            data[name] = values if len(values) > 1 else values[0]
        resolve_type(node.type_specifier)  # unknown type -> error
        return [Node(data, node.type_specifier.name)]

    # ------------------------------------------------------------- binary
    def _binary(self, node: ast.Binary, ctx: EvalContext) -> List[Any]:
        op = node.op
        if op in _LOGIC:
            return self._logic(node, ctx)
        left = self.evaluate(node.left, ctx)
        right = self.evaluate(node.right, ctx)
        if op == "|":
            return equality.distinct(left + right)
        if op in _EQUALITY:
            if op in ("=", "!="):
                result = equality.equal_collections(left, right)
                if result is None:
                    return []
                return [result if op == "=" else not result]
            result = equality.equivalent_collections(left, right)
            return [result if op == "~" else not result]
        if op in comparison.OPERATORS:
            a = singleton(left, "left operand of '%s'" % op)
            b = singleton(right, "right operand of '%s'" % op)
            if a is MISSING or b is MISSING:
                return []
            outcome = comparison.compare(a, b)
            return [] if outcome is None else [comparison.OPERATORS[op](outcome)]
        if op == "in":
            item = singleton(left, "left operand of 'in'")
            if item is MISSING:
                return []
            return [equality.contains_item(right, item)]
        if op == "contains":
            item = singleton(right, "right operand of 'contains'")
            if item is MISSING:
                return []
            return [equality.contains_item(left, item)]
        if op == "&":
            a = singleton_value(left, "left operand of '&'")
            b = singleton_value(right, "right operand of '&'")
            for value in (a, b):
                if value is not MISSING and not isinstance(value, str):
                    raise EvaluationError("operator '&' requires String operands")
            return [(a or "") + (b or "")]
        if op in _MATH:
            a = singleton_value(left, "left operand of '%s'" % op)
            b = singleton_value(right, "right operand of '%s'" % op)
            if a is MISSING or b is MISSING:
                return []
            result = arithmetic.apply(op, a, b)
            return [] if result is None else [result]
        raise EvaluationError("unknown operator '%s'" % op)

    def _logic(self, node: ast.Binary, ctx: EvalContext) -> List[Any]:
        op = node.op
        left = singleton_boolean(
            self.evaluate(node.left, ctx), "left operand of '%s'" % op
        )
        if op == "implies" and left is False:
            return [True]
        right = singleton_boolean(
            self.evaluate(node.right, ctx), "right operand of '%s'" % op
        )
        if op == "and":
            if left is False or right is False:
                return [False]
            if left is True and right is True:
                return [True]
            return []
        if op == "or":
            if left is True or right is True:
                return [True]
            if left is False and right is False:
                return [False]
            return []
        if op == "xor":
            if left is MISSING or right is MISSING:
                return []
            return [left != right]
        # implies (left is True or MISSING)
        if left is True:
            return [] if right is MISSING else [right]
        return [True] if right is True else []

    _dispatch = {
        ast.Literal: _literal,
        ast.ExternalConstant: _external,
        ast.Indexer: _indexer,
        ast.Unary: _unary,
        ast.Binary: _binary,
        ast.TypeOperation: _type_operation,
        ast.InstanceSelector: _instance_selector,
    }


def _wrap(value: Any) -> Any:
    """Host-supplied variable value -> collection item."""
    if isinstance(
        value, (Node, str, bool, int, Decimal, FPDate, FPDateTime, FPTime, Quantity)
    ):
        return value
    if isinstance(value, float):
        return Decimal(repr(value))
    return Node.root(value)


def _root_resource(node: Node) -> Node:
    """The outermost resource (container of contained resources)."""
    current, top = node, node
    while current is not None:
        if current.is_resource:
            top = current
            if current.name != "contained":
                # a resource reached through Bundle.entry.resource is its own root
                if current.parent is not None and current.name == "resource":
                    break
        current = current.parent
    return top


def to_json(value: Any) -> Any:
    """Collection item -> JSON-like value (instance selectors, public output)."""
    if isinstance(value, Node):
        if value.is_primitive:
            converted = system(value)
            return None if converted is MISSING else to_json(converted)
        raw = value.value
        if hasattr(raw, "model_dump"):
            return raw.model_dump(mode="python", by_alias=True, exclude_none=True)
        return raw
    if isinstance(value, (FPDate, FPDateTime, FPTime)):
        return value.isoformat()
    if isinstance(value, Quantity):
        result = {"value": value.value}
        if value.is_calendar:
            result["unit"] = value.unit
        else:
            result.update(
                unit=value.unit, system="http://unitsofmeasure.org", code=value.unit
            )
        return result
    return value


__all__ = ["Engine", "to_json"]
