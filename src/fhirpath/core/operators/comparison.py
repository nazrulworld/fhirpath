# _*_ coding: utf-8 _*_
"""``<`` ``<=`` ``>`` ``>=`` ordering."""

from typing import Any, Optional

from ..evaluation import EvaluationError
from ..model import Node
from ..types import FPDate, FPDateTime, FPTime, Quantity
from ..values import MISSING, is_number, promote, system
from . import quantity as quantity_ops
from . import temporal

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

_TEMPORAL = (FPDate, FPDateTime, FPTime)


def compare(a: Any, b: Any, expression: str = "") -> Optional[int]:
    """-1/0/1, ``None`` when unknown (precision / incommensurable units).

    Raises :class:`EvaluationError` for operands that cannot be compared.
    """
    a, b = system(a), system(b)
    if a is MISSING or b is MISSING:
        return None
    if (
        isinstance(a, bool)
        or isinstance(b, bool)
        or isinstance(a, Node)
        or isinstance(b, Node)
    ):
        raise EvaluationError(
            "cannot compare %s with %s" % (_name(a), _name(b)), expression
        )
    a, b = promote(a, b)
    if is_number(a) and is_number(b):
        return (a > b) - (a < b)
    if isinstance(a, str) and isinstance(b, str):
        return (a > b) - (a < b)
    if isinstance(a, _TEMPORAL) and isinstance(b, _TEMPORAL) and type(a) is type(b):
        return temporal.compare(a, b)
    if isinstance(a, Quantity) and isinstance(b, Quantity):
        return quantity_ops.compare(a, b)
    raise EvaluationError(
        "cannot compare %s with %s" % (_name(a), _name(b)), expression
    )


def _name(value: Any) -> str:
    if isinstance(value, Node):
        return value.type_name or "element"
    return type(value).__name__


OPERATORS = {
    "<": lambda c: c < 0,
    "<=": lambda c: c <= 0,
    ">": lambda c: c > 0,
    ">=": lambda c: c >= 0,
}

__all__ = ["compare", "OPERATORS"]
