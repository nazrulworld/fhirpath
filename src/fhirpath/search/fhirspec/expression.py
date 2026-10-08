# _*_ coding: utf-8 _*_
"""``SearchParameter.expression`` handling, based on the FHIRPath parser of
:mod:`fhirpath.core`, for every FHIR release.

Releases write the same thing differently: STU3 ``Condition.abatement.as(Age)``,
R4/R4B ``(Condition.abatement as Age)``, R5 ``Condition.abatement.ofType(Age)``;
shared definitions join one branch per base resource with ``|`` and R5 even has a
branch without its resource name (``(start | requestedPeriod.start).first()`` for
Appointment in ``clinical-date``). This module

* splits a definition's expression per base resource (:func:`split_by_base`), and
* turns a resource's expression into the dotted element paths the FQL layer
  searches on (:func:`element_paths`): ``Observation.value.ofType(Quantity)`` ->
  ``Observation.valueQuantity``.
"""

import logging
from decimal import Decimal
from typing import Dict, Iterable, List, Optional

from fhirpath.core import ast
from fhirpath.core.parser import parse

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.fhirspec.expression")

# a type cast selects the typed name of a choice element (value + Quantity)
CAST_FUNCTIONS = ("ofType", "as")
# functions that only narrow a selection; searching on all values is a superset
IGNORED_FUNCTIONS = ("first",)


class UnsupportedExpression(ValueError):
    """The expression cannot be expressed as an element path."""


# ---------------------------------------------------------------- unparsing


def _quote(value: str) -> str:
    return "'%s'" % value.replace("\\", "\\\\").replace("'", "\\'")


def _operand(node: ast.Node) -> str:
    text = to_expression(node)
    if isinstance(node, (ast.Binary, ast.TypeOperation, ast.Unary)):
        return "(%s)" % text
    return text


def to_expression(node: ast.Node) -> str:
    """FHIRPath text of an AST (parentheses only where an operand needs them)."""
    if isinstance(node, ast.Member):
        return node.name
    if isinstance(node, ast.Invocation):
        return "%s.%s" % (_operand(node.left), to_expression(node.right))
    if isinstance(node, ast.Function):
        return "%s(%s)" % (node.name, ", ".join(to_expression(a) for a in node.args))
    if isinstance(node, ast.Indexer):
        return "%s[%s]" % (_operand(node.left), to_expression(node.index))
    if isinstance(node, ast.Binary):
        return "%s %s %s" % (_operand(node.left), node.op, _operand(node.right))
    if isinstance(node, ast.TypeOperation):
        return "%s %s %s" % (_operand(node.left), node.op, node.type_specifier)
    if isinstance(node, ast.Unary):
        return "%s%s" % (node.op, _operand(node.operand))
    if isinstance(node, ast.Literal):
        value = node.value
        if value is None:
            return "{}"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return _quote(value)
        if isinstance(value, (int, Decimal)):
            return str(value)
        raise UnsupportedExpression("cannot write literal %r" % (value,))
    if isinstance(node, ast.ExternalConstant):
        return "%" + node.name
    if isinstance(node, ast.This):
        return "$this"
    if isinstance(node, ast.Index):
        return "$index"
    if isinstance(node, ast.Total):
        return "$total"
    raise UnsupportedExpression("cannot write %s" % type(node).__name__)


# ------------------------------------------------------------ union branches


def union_branches(node: ast.Node) -> List[ast.Node]:
    """Top-level ``|`` operands (parentheses are not kept by the parser)."""
    if isinstance(node, ast.Binary) and node.op == "|":
        return union_branches(node.left) + union_branches(node.right)
    return [node]


def root_name(node: ast.Node) -> Optional[str]:
    """Name of the first member of a path (``Observation`` for
    ``Observation.value.ofType(Quantity)``); ``None`` when it does not start with
    a member (unions, literals...)."""
    while True:
        if isinstance(node, ast.Member):
            return node.name
        if isinstance(node, (ast.Invocation, ast.Indexer)):
            node = node.left
        elif isinstance(node, ast.TypeOperation):
            node = node.left
        else:
            return None


def prefix_paths(node: ast.Node, anchor: ast.Node) -> ast.Node:
    """Anchor a relative expression to ``anchor`` (a resource type or an element
    path): ``(start | requestedPeriod.start).first()`` anchored to ``Appointment``
    is ``(Appointment.start | Appointment.requestedPeriod.start).first()``.
    ``%resource`` / ``%rootResource`` stand for the resource the anchor starts at.
    """
    if isinstance(node, ast.Member):
        return ast.Invocation(anchor, node)
    if isinstance(node, ast.ExternalConstant) and node.name in (
        "resource",
        "rootResource",
    ):
        name = root_name(anchor)
        if name is None:
            raise UnsupportedExpression("cannot resolve %" + node.name)
        return ast.Member(name)
    if isinstance(node, ast.Invocation):
        return ast.Invocation(prefix_paths(node.left, anchor), node.right)
    if isinstance(node, ast.Indexer):
        return ast.Indexer(prefix_paths(node.left, anchor), node.index)
    if isinstance(node, ast.TypeOperation):
        return ast.TypeOperation(
            node.op, prefix_paths(node.left, anchor), node.type_specifier
        )
    if isinstance(node, ast.Binary) and node.op == "|":
        return ast.Binary(
            "|", prefix_paths(node.left, anchor), prefix_paths(node.right, anchor)
        )
    raise UnsupportedExpression(
        "cannot anchor %s to %s" % (to_expression(node), to_expression(anchor))
    )


def component_paths(base_path: str, component_expression: str) -> List[str]:
    """Element paths of a composite component, whose expression is relative to
    the composite's base path: ``Group.characteristic`` +
    ``(value as CodeableConcept) | (value as boolean)`` ->
    ``Group.characteristic.valueCodeableConcept``,
    ``Group.characteristic.valueBoolean``."""
    anchored = prefix_paths(parse(component_expression), parse(base_path))
    return element_paths(to_expression(anchored))


def split_by_base(expression: str, bases: Iterable[str]) -> Dict[str, str]:
    """Expression of each base resource of a (shared) search parameter.

    Branches are assigned by their first member; a definition with one base gets
    the whole expression. A branch that does not start with a base name (R5
    ``clinical-date`` for Appointment) is anchored to a base that has no branch of
    its own: branches follow the order of ``base``, so the candidates are the
    bases without a branch between the bases of its neighbouring branches. When
    that is ambiguous the branch is dropped with a warning. Bases without any
    branch are left out of the result.
    """
    bases = list(bases)
    tree = parse(expression)
    if len(bases) == 1:
        return {bases[0]: to_expression(tree)}

    branches = [(root_name(b), b) for b in union_branches(tree)]
    per_base: Dict[str, List[ast.Node]] = {}
    for name, branch in branches:
        if name in bases:
            per_base.setdefault(name, []).append(branch)

    for position, (name, branch) in enumerate(branches):
        if name in bases:
            continue
        before = [n for n, _ in branches[:position] if n in bases]
        after = [n for n, _ in branches[position + 1 :] if n in bases]
        low = bases.index(before[-1]) + 1 if before else 0
        high = bases.index(after[0]) if after else len(bases)
        candidates = [b for b in bases[low:high] if b not in per_base]
        if len(candidates) == 1:
            per_base[candidates[0]] = [prefix_paths(branch, ast.Member(candidates[0]))]
        else:
            logger.warning(
                "dropping search expression branch without a base resource: %s",
                to_expression(branch),
            )

    return {
        base: " | ".join(to_expression(branch) for branch in branches)
        for base, branches in per_base.items()
    }


# ------------------------------------------------------------- element paths


def _typed_name(name: str, type_name: str) -> str:
    return name + type_name[0].upper() + type_name[1:]


def _cast_type(function: ast.Function) -> Optional[str]:
    if function.name in CAST_FUNCTIONS and len(function.args) == 1:
        arg = function.args[0]
        if isinstance(arg, ast.Member):
            return arg.name
    return None


def _where_suffix(function: ast.Function) -> str:
    """``where(...)`` filters the FQL ``ElementPath`` understands:
    ``where(resolve() is Patient)`` and ``where(name = 'literal')``."""
    if len(function.args) == 1:
        test = function.args[0]
        if (
            isinstance(test, ast.TypeOperation)
            and test.op == "is"
            and isinstance(test.left, ast.Function)
            and test.left.name == "resolve"
            and not test.left.args
        ):
            return ".where(resolve() is %s)" % test.type_specifier.name
        if (
            isinstance(test, ast.Binary)
            and test.op == "="
            and isinstance(test.left, ast.Member)
            and isinstance(test.right, ast.Literal)
            and isinstance(test.right.value, str)
        ):
            return ".where(%s=%s)" % (test.left.name, _quote(test.right.value))
    raise UnsupportedExpression("unsupported filter %s" % to_expression(function))


def _paths(node: ast.Node) -> List[str]:
    if isinstance(node, ast.Member):
        return [node.name]

    if isinstance(node, ast.Binary) and node.op == "|":
        return _paths(node.left) + _paths(node.right)

    if isinstance(node, ast.TypeOperation) and node.op == "as":
        return [_cast(path, node.type_specifier.name) for path in _paths(node.left)]

    if isinstance(node, ast.Indexer):
        # kept as text: the FQL path layer decides what to do with it
        return [
            "%s[%s]" % (path, to_expression(node.index)) for path in _paths(node.left)
        ]

    if isinstance(node, ast.Invocation):
        lefts = _paths(node.left)
        right = node.right
        if isinstance(right, ast.Member):
            for path in lefts:
                if ".where(" in path:
                    raise UnsupportedExpression(
                        "unsupported navigation after a filter: %s"
                        % to_expression(node)
                    )
            return ["%s.%s" % (path, right.name) for path in lefts]
        if isinstance(right, ast.Function):
            cast = _cast_type(right)
            if cast is not None:
                return [_cast(path, cast) for path in lefts]
            if right.name in IGNORED_FUNCTIONS and not right.args:
                return lefts
            if right.name == "where":
                suffix = _where_suffix(right)
                return [path + suffix for path in lefts]
        raise UnsupportedExpression("unsupported %s" % to_expression(node))

    raise UnsupportedExpression("unsupported %s" % to_expression(node))


def _cast(path: str, type_name: str) -> str:
    """Select a choice type: ``Observation.value`` + ``Quantity`` ->
    ``Observation.valueQuantity``."""
    if ".where(" in path or path.endswith("]"):
        raise UnsupportedExpression("unsupported type cast on %s" % path)
    head, _, name = path.rpartition(".")
    typed = _typed_name(name, type_name)
    return "%s.%s" % (head, typed) if head else typed


def element_paths(expression: str) -> List[str]:
    """Dotted element paths of a resource's search expression, one per branch.

    Branches that cannot be written as an element path (computed values such as
    ``Patient.deceased.exists() and Patient.deceased != false``, extension
    lookups...) are left out; :class:`UnsupportedExpression` is raised when none
    is left.
    """
    paths: List[str] = []
    errors: List[str] = []
    for branch in union_branches(parse(expression)):
        try:
            paths.extend(p for p in _paths(branch) if p not in paths)
        except UnsupportedExpression as exc:
            errors.append(str(exc))
    if not paths:
        raise UnsupportedExpression(
            "no element path in '%s' (%s)" % (expression, "; ".join(errors))
        )
    if errors:
        logger.debug("ignored search expression branches: %s", "; ".join(errors))
    return paths
