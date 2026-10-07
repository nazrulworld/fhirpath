# _*_ coding: utf-8 _*_
"""Math functions (abs, ceiling, exp, floor, ln, log, power, round, sqrt, truncate)."""

from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    Decimal,
    InvalidOperation,
    localcontext,
)

from ..types import Long, Quantity, round_half_away
from ..values import MISSING, as_decimal, is_integer, is_number
from .registry import Call, function

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


def _number(call: Call, allow_quantity: bool = True):
    value = call.input_value()
    if value is MISSING:
        return MISSING
    if isinstance(value, bool) or not (
        is_number(value) or (allow_quantity and isinstance(value, Quantity))
    ):
        raise call.error(
            "input must be a number%s" % (" or Quantity" if allow_quantity else "")
        )
    return value


def _apply(value, fn):
    """Apply ``fn`` to a number or a Quantity's value (keeping the unit)."""
    if isinstance(value, Quantity):
        result = fn(value.value)
        return None if result is None else Quantity(Decimal(result), value.unit)
    return fn(value)


def _wrap(result):
    return [] if result is None else [result]


@function("abs")
def abs_(call: Call):
    value = _number(call)
    if value is MISSING:
        return []
    if isinstance(value, Long):
        return [Long(abs(value))]
    return _wrap(_apply(value, abs))


def _rounding(rounding):
    def fn(number):
        if is_integer(number):
            return int(number)
        return int(Decimal(number).to_integral_value(rounding=rounding))

    return fn


@function("ceiling")
def ceiling(call: Call):
    value = _number(call)
    return [] if value is MISSING else _wrap(_apply(value, _rounding(ROUND_CEILING)))


@function("floor")
def floor(call: Call):
    value = _number(call)
    return [] if value is MISSING else _wrap(_apply(value, _rounding(ROUND_FLOOR)))


@function("truncate")
def truncate(call: Call):
    value = _number(call)
    return [] if value is MISSING else _wrap(_apply(value, _rounding(ROUND_DOWN)))


def _decimal_op(fn):
    def apply(number):
        with localcontext() as ctx:
            ctx.prec = 28
            try:
                return fn(as_decimal(number))
            except (InvalidOperation, ArithmeticError, ValueError):
                return None

    return apply


@function("exp")
def exp(call: Call):
    value = _number(call, allow_quantity=False)
    return [] if value is MISSING else _wrap(_decimal_op(lambda d: d.exp())(value))


@function("ln")
def ln(call: Call):
    value = _number(call, allow_quantity=False)
    if value is MISSING:
        return []
    if value <= 0:
        return []
    return _wrap(_decimal_op(lambda d: d.ln())(value))


@function("log", 1)
def log(call: Call):
    value = _number(call, allow_quantity=False)
    base = call.arg_value(0)
    if value is MISSING or base is MISSING:
        return []
    if isinstance(base, bool) or not is_number(base):
        raise call.error("base must be a number")
    if value <= 0 or base <= 0 or base == 1:
        raise call.error("logarithm undefined for input %s and base %s" % (value, base))
    return _wrap(_decimal_op(lambda d: d.ln() / as_decimal(base).ln())(value))


@function("power", 1)
def power(call: Call):
    value = _number(call, allow_quantity=False)
    exponent = call.arg_value(0)
    if value is MISSING or exponent is MISSING:
        return []
    if isinstance(exponent, bool) or not is_number(exponent):
        raise call.error("exponent must be a number")
    if is_integer(value) and is_integer(exponent) and exponent >= 0:
        result = int(value) ** int(exponent)
        return [Long(result) if isinstance(value, Long) else result]
    base, exp_ = as_decimal(value), as_decimal(exponent)
    if base < 0 and exp_ != exp_.to_integral_value():
        return []
    if base == 0 and exp_ < 0:
        return []
    return _wrap(_decimal_op(lambda d: d**exp_)(base))


@function("round", 0, 1)
def round_(call: Call):
    value = _number(call)
    if value is MISSING:
        return []
    precision = call.arg_integer(0) if call.has_arg(0) else 0
    if precision is MISSING:
        precision = 0
    if precision < 0:
        raise call.error("precision must be >= 0")
    return _wrap(_apply(value, lambda n: round_half_away(as_decimal(n), precision)))


@function("sqrt")
def sqrt(call: Call):
    value = _number(call, allow_quantity=False)
    if value is MISSING:
        return []
    if value < 0:
        return []
    return _wrap(_decimal_op(lambda d: d.sqrt())(value))
