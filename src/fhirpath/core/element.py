# _*_ coding: utf-8 _*_
"""Public entry points of the FHIRPath engine.

>>> from fhirpath.core import evaluate
>>> evaluate(patient, "name.where(use = 'official').given.first()")
['Peter']

Results are plain values: System values (``str``, ``bool``, ``int``,
:class:`~fhirpath.core.types.Long`, ``Decimal``, :class:`~fhirpath.core.types.FPDate`,
:class:`~fhirpath.core.types.FPDateTime`, :class:`~fhirpath.core.types.FPTime`,
:class:`~fhirpath.core.types.Quantity`) for primitives, and the original
model instance (or dict) for complex elements. Use ``nodes=True`` to get the
underlying :class:`~fhirpath.core.model.Node` objects instead.
"""

from typing import Any, Dict, List, Optional

from .context import Environment, Resolver, Terminology, Tracer
from .engine import Engine
from .evaluation import EvaluationError
from .parser import parse
from .types import FPDateTime
from .values import to_output

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

_ENGINE = Engine()


class CompiledExpression:
    """A parsed expression that can be evaluated many times."""

    __slots__ = ("expression", "tree")

    def __init__(self, expression: str):
        self.expression = expression
        self.tree = parse(expression)

    def __repr__(self):
        return "CompiledExpression(%r)" % self.expression

    def evaluate(
        self,
        resource: Any = None,
        variables: Optional[Dict[str, Any]] = None,
        *,
        resolver: Optional[Resolver] = None,
        terminology: Optional[Terminology] = None,
        tracer: Optional[Tracer] = None,
        now: Optional[FPDateTime] = None,
        nodes: bool = False,
    ) -> List[Any]:
        env = Environment(
            now=now, resolver=resolver, tracer=tracer, terminology=terminology
        )
        try:
            result = _ENGINE.run(self.tree, resource, variables, env)
        except EvaluationError as exc:
            if not exc.expression:
                exc.expression = self.expression
            raise
        if nodes:
            return result
        outputs = []
        for item in result:
            value = to_output(item)
            if value is not None:
                outputs.append(value)
        return outputs

    def test(
        self,
        resource: Any = None,
        variables: Optional[Dict[str, Any]] = None,
        **options,
    ) -> bool:
        """Evaluate as a predicate (e.g. an invariant): single Boolean or non-empty."""
        result = self.evaluate(resource, variables, **options)
        if len(result) == 1 and isinstance(result[0], bool):
            return result[0]
        return len(result) > 0


def compile(expression: str) -> CompiledExpression:  # noqa: A001 - mirrors re.compile
    return CompiledExpression(expression)


def evaluate(
    resource: Any,
    expression: str,
    variables: Optional[Dict[str, Any]] = None,
    **options,
) -> List[Any]:
    """Evaluate ``expression`` against ``resource`` (model instance, dict or None)."""
    return CompiledExpression(expression).evaluate(resource, variables, **options)


class Element:
    """Convenience wrapper binding a resource to the engine."""

    __slots__ = ("__value__",)

    def __init__(self, value: Any):
        object.__setattr__(self, "__value__", value)

    def __setattr__(self, key, value):
        raise TypeError("Readonly object!")

    def element_value(self) -> Any:
        return self.__value__

    def query(
        self, expression: str, variables: Optional[Dict[str, Any]] = None, **options
    ) -> List[Any]:
        return evaluate(self.__value__, expression, variables, **options)

    def test(
        self, expression: str, variables: Optional[Dict[str, Any]] = None, **options
    ) -> bool:
        return CompiledExpression(expression).test(self.__value__, variables, **options)


__all__ = ["Element", "CompiledExpression", "compile", "evaluate", "to_output"]
