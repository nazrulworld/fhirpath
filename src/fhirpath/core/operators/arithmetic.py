# _*_ coding: utf-8 _*_
"""Math operators: ``* / div mod + - &`` and unary ``+``/``-``.

Each function takes System values (never empty) and returns a System value, or
``None`` for an empty result (division by zero, overflow, incompatible units).
"""

from decimal import ROUND_DOWN, Decimal, DivisionByZero, InvalidOperation, localcontext
from typing import Any, Optional

from ..evaluation import EvaluationError
from ..types import (
    INTEGER_MAX,
    INTEGER_MIN,
    LONG_MAX,
    LONG_MIN,
    FPDate,
    FPDateTime,
    FPTime,
    Long,
    Quantity,
)
from ..values import is_integer, is_number, promote
from . import quantity as quantity_ops
from . import temporal

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

_TEMPORAL = (FPDate, FPDateTime, FPTime)


def _type_error(op: str, a: Any, b: Any, expression: str):
    raise EvaluationError(
        "operator '%s' cannot be applied to %s and %s"
        % (op, type(a).__name__, type(b).__name__),
        expression,
    )


def _check_integer(value: int, template: Any) -> Optional[int]:
    if isinstance(template, Long):
        return Long(value) if LONG_MIN <= value <= LONG_MAX else None
    return value if INTEGER_MIN <= value <= INTEGER_MAX else None


def _numeric(op: str, a: Any, b: Any) -> Optional[Any]:
    if isinstance(a, Decimal):
        with localcontext() as ctx:
            ctx.prec = 28
            try:
                if op == "+":
                    return a + b
                if op == "-":
                    return a - b
                if op == "*":
                    return a * b
            except (InvalidOperation, ArithmeticError):
                return None
    if op == "+":
        return _check_integer(int(a) + int(b), a)
    if op == "-":
        return _check_integer(int(a) - int(b), a)
    if op == "*":
        return _check_integer(int(a) * int(b), a)
    raise AssertionError(op)


def apply(op: str, a: Any, b: Any, expression: str = "") -> Optional[Any]:
    if op == "&":
        return (a or "") + (b or "")
    if isinstance(a, bool) or isinstance(b, bool):
        _type_error(op, a, b, expression)
    if op in ("+", "-") and isinstance(a, _TEMPORAL):
        if not isinstance(b, Quantity):
            _type_error(op, a, b, expression)
        return temporal.add(a, b, 1 if op == "+" else -1, expression)
    a, b = promote(a, b)
    if op == "+" and isinstance(a, str) and isinstance(b, str):
        return a + b
    if is_number(a) and is_number(b):
        if op in ("+", "-", "*"):
            return _numeric(op, a, b)
        if op == "/":
            return _divide(Decimal(a), Decimal(b))
        if op == "div":
            return _integer_divide(a, b)
        if op == "mod":
            return _modulo(a, b)
    if isinstance(a, Quantity) and isinstance(b, Quantity):
        if op == "+":
            return quantity_ops.add(a, b, 1)
        if op == "-":
            return quantity_ops.add(a, b, -1)
        if op == "*":
            return quantity_ops.multiply(a, b)
        if op == "/":
            return quantity_ops.multiply(a, b, divide=True)
    _type_error(op, a, b, expression)


def _divide(a: Decimal, b: Decimal) -> Optional[Decimal]:
    if b == 0:
        return None
    with localcontext() as ctx:
        ctx.prec = 28
        try:
            result = a / b
        except (InvalidOperation, DivisionByZero, ArithmeticError):
            return None
    if result == result.to_integral_value() and result.as_tuple().exponent > -1:
        return result.quantize(Decimal("1.0"))
    return result


def _integer_divide(a: Any, b: Any) -> Optional[Any]:
    if b == 0:
        return None
    if isinstance(a, Decimal) or isinstance(b, Decimal):
        return (Decimal(a) / Decimal(b)).to_integral_value(rounding=ROUND_DOWN)
    quotient = abs(int(a)) // abs(int(b))
    if (a < 0) != (b < 0):
        quotient = -quotient
    return _check_integer(quotient, a)


def _modulo(a: Any, b: Any) -> Optional[Any]:
    if b == 0:
        return None
    if isinstance(a, Decimal) or isinstance(b, Decimal):
        return Decimal(a) % Decimal(b)  # Decimal % truncates (sign of dividend)
    result = abs(int(a)) % abs(int(b))
    return _check_integer(-result if a < 0 else result, a)


def negate(value: Any, expression: str = "") -> Optional[Any]:
    if isinstance(value, bool):
        raise EvaluationError("unary '-' cannot be applied to Boolean", expression)
    if is_integer(value):
        return _check_integer(-int(value), value)
    if isinstance(value, Decimal):
        return -value
    if isinstance(value, Quantity):
        return Quantity(-value.value, value.unit)
    raise EvaluationError(
        "unary '-' cannot be applied to %s" % type(value).__name__, expression
    )


def positive(value: Any, expression: str = "") -> Any:
    if isinstance(value, bool) or not (is_number(value) or isinstance(value, Quantity)):
        raise EvaluationError(
            "unary '+' cannot be applied to %s" % type(value).__name__, expression
        )
    return value


__all__ = ["apply", "negate", "positive"]
