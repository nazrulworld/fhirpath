# _*_ coding: utf-8 _*_
"""Date/DateTime/Time comparison and arithmetic with partial precision."""

import datetime
from decimal import ROUND_DOWN, Decimal
from typing import Optional

from ..evaluation import EvaluationError
from ..types import (
    DAY,
    HOUR,
    MILLISECOND,
    MINUTE,
    MONTH,
    SECOND,
    YEAR,
    FPDateTime,
    FPTime,
    Quantity,
    _Temporal,
    days_in_month,
)

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


def _same_kind(a: _Temporal, b: _Temporal) -> bool:
    return type(a) is type(b)


def to_utc(value: _Temporal) -> _Temporal:
    """Shift a DateTime with an offset (and at least hour precision) to UTC."""
    if (
        not isinstance(value, FPDateTime)
        or value.tz in (None, 0)
        or value.precision < HOUR
    ):
        return value
    shifted = value.to_datetime() - datetime.timedelta(minutes=value.tz)
    return value.replace(
        year=shifted.year,
        month=shifted.month,
        day=shifted.day,
        hour=shifted.hour,
        minute=shifted.minute if value.precision >= MINUTE else None,
        second=value.second,
        millisecond=value.millisecond,
        tz=0,
    )


def _seconds(value: _Temporal) -> Decimal:
    return Decimal(value.second) + Decimal(value.millisecond or 0) / Decimal(1000)


def compare(a: _Temporal, b: _Temporal) -> Optional[int]:
    """-1/0/1, or ``None`` when the precision difference makes it uncertain.

    Raises ``TypeError`` for different temporal kinds (caller decides).
    """
    if not _same_kind(a, b):
        raise TypeError("different temporal types")
    if isinstance(a, FPDateTime) and a.precision >= HOUR and b.precision >= HOUR:
        if (a.tz is None) != (b.tz is None):
            return None
        a, b = to_utc(a), to_utc(b)
    for level in range(a.LOW, SECOND + 1):
        has_a, has_b = a.precision >= level, b.precision >= level
        if not has_a and not has_b:
            return 0
        if has_a != has_b:
            return None
        if level == SECOND:
            va, vb = _seconds(a), _seconds(b)
        else:
            va, vb = getattr(a, _NAMES[level]), getattr(b, _NAMES[level])
        if va != vb:
            return -1 if va < vb else 1
    return 0


_NAMES = ("year", "month", "day", "hour", "minute", "second", "millisecond")


def equals(a: _Temporal, b: _Temporal) -> Optional[bool]:
    try:
        result = compare(a, b)
    except TypeError:
        return False
    return None if result is None else result == 0


def equivalent(a: _Temporal, b: _Temporal) -> bool:
    return bool(equals(a, b))


# ---------------------------------------------------------------------------
# arithmetic
# ---------------------------------------------------------------------------

_UCUM_TIME = {
    "wk": "week",
    "d": "day",
    "h": "hour",
    "min": "minute",
    "s": "second",
    "ms": "millisecond",
}
_UNIT_LEVEL = {
    "year": YEAR,
    "month": MONTH,
    "week": DAY,
    "day": DAY,
    "hour": HOUR,
    "minute": MINUTE,
    "second": SECOND,
    "millisecond": MILLISECOND,
}
#: duration of a unit in milliseconds (week..millisecond)
_MS = {
    "week": 7 * 86400000,
    "day": 86400000,
    "hour": 3600000,
    "minute": 60000,
    "second": 1000,
    "millisecond": 1,
}
_LEVEL_UNIT = {
    DAY: "day",
    HOUR: "hour",
    MINUTE: "minute",
    SECOND: "second",
    MILLISECOND: "millisecond",
}


def _calendar_unit(quantity: Quantity, expression: str) -> str:
    unit = quantity.unit
    if quantity.is_calendar:
        return unit
    if unit in _UCUM_TIME:
        return _UCUM_TIME[unit]
    raise EvaluationError(
        "cannot add quantity with unit '%s' to a date/time value" % unit, expression
    )


def add(
    value: _Temporal, quantity: Quantity, sign: int, expression: str = ""
) -> _Temporal:
    unit = _calendar_unit(quantity, expression)
    if isinstance(value, FPTime) and unit in ("year", "month", "week", "day"):
        raise EvaluationError("cannot add '%s' to a Time" % unit, expression)
    amount = quantity.value * sign
    precision = value.precision
    # bring the quantity to the value's precision when it is finer
    if _UNIT_LEVEL[unit] > precision or (unit == "week" and precision < DAY):
        amount, unit = _coarsen(amount, unit, precision)
    if unit in ("year", "month"):
        return _add_months(
            value,
            int(amount.to_integral_value(ROUND_DOWN)) * (12 if unit == "year" else 1),
            expression,
        )
    if unit in ("second",):
        milliseconds = int((amount * 1000).to_integral_value(ROUND_DOWN))
    else:
        milliseconds = int(amount.to_integral_value(ROUND_DOWN)) * _MS[unit]
    return _add_milliseconds(value, milliseconds, expression)


def _coarsen(amount: Decimal, unit: str, precision: int):
    """Express ``amount unit`` in the unit of ``precision`` (truncating)."""
    if precision == YEAR:
        if unit == "month":
            return (amount / 12).to_integral_value(ROUND_DOWN), "year"
        days = amount * _MS[unit] / _MS["day"]
        return (days / 365).to_integral_value(ROUND_DOWN), "year"
    if precision == MONTH:
        days = amount * _MS[unit] / _MS["day"]
        return (days / 30).to_integral_value(ROUND_DOWN), "month"
    target = _LEVEL_UNIT[precision]
    return (amount * _MS[unit] / _MS[target]).to_integral_value(ROUND_DOWN), target


def _add_months(value: _Temporal, months: int, expression: str) -> _Temporal:
    total = value.year * 12 + (value.month or 1) - 1 + months
    year, month = divmod(total, 12)
    month += 1
    if not 1 <= year <= 9999:
        raise EvaluationError("date arithmetic out of range", expression)
    kwargs = {"year": year}
    if value.precision >= MONTH:
        kwargs["month"] = month
    if value.precision >= DAY:
        kwargs["day"] = min(value.day, days_in_month(year, month))
    return value.replace(**kwargs)


def _add_milliseconds(
    value: _Temporal, milliseconds: int, expression: str
) -> _Temporal:
    if isinstance(value, FPTime):
        base = datetime.datetime(
            2000,
            1,
            1,
            value.hour,
            value.minute or 0,
            value.second or 0,
            (value.millisecond or 0) * 1000,
        )
        result = base + datetime.timedelta(milliseconds=milliseconds)
        return _from_python(value, result)
    base = datetime.datetime(
        value.year,
        value.month or 1,
        value.day or 1,
        value.hour or 0,
        value.minute or 0,
        value.second or 0,
        (value.millisecond or 0) * 1000,
    )
    try:
        result = base + datetime.timedelta(milliseconds=milliseconds)
    except OverflowError:
        raise EvaluationError("date arithmetic out of range", expression)
    return _from_python(value, result)


def _from_python(template: _Temporal, result: datetime.datetime) -> _Temporal:
    p = template.precision
    values = {}
    for level, name in enumerate(_NAMES):
        if level < template.LOW:
            continue
        if level <= p:
            values[name] = (
                result.microsecond // 1000
                if name == "millisecond"
                else getattr(result, name)
            )
    return template.replace(**values)


__all__ = ["compare", "equals", "equivalent", "add", "to_utc"]
