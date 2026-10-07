# _*_ coding: utf-8 _*_
"""Date/time component extraction, boundaries, precision, duration/difference."""

import datetime
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, Decimal
from typing import Any, Optional

from ..operators import quantity as quantity_ops
from ..operators.temporal import to_utc
from ..types import (
    DAY,
    HOUR,
    MILLISECOND,
    MINUTE,
    MONTH,
    SECOND,
    YEAR,
    FPDate,
    FPDateTime,
    FPTime,
    Quantity,
    days_in_month,
    decimal_places,
)
from ..values import MISSING, as_decimal, as_quantity, is_integer, is_number
from .registry import Call, function

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

_TEMPORAL = (FPDate, FPDateTime, FPTime)

# ---------------------------------------------------------- component access


def _component(name: str, kinds, attribute: str, level: int):
    def impl(call: Call):
        value = call.input_value()
        if value is MISSING or not isinstance(value, kinds):
            return []
        if value.precision < level:
            return []
        return [getattr(value, attribute)]

    function(name)(impl)


_component("yearOf", (FPDate, FPDateTime), "year", YEAR)
_component("monthOf", (FPDate, FPDateTime), "month", MONTH)
_component("dayOf", (FPDate, FPDateTime), "day", DAY)
_component("hourOf", (FPDateTime, FPTime), "hour", HOUR)
_component("minuteOf", (FPDateTime, FPTime), "minute", MINUTE)
_component("secondOf", (FPDateTime, FPTime), "second", SECOND)
_component("millisecondOf", (FPDateTime, FPTime), "millisecond", MILLISECOND)


@function("timezoneOffsetOf")
def timezone_offset_of(call: Call):
    value = call.input_value()
    if not isinstance(value, FPDateTime) or value.tz is None:
        return []
    return [Decimal(value.tz) / Decimal(60)]


@function("dateOf")
def date_of(call: Call):
    value = call.input_value()
    if isinstance(value, FPDateTime):
        return [value.to_date()]
    if isinstance(value, FPDate):
        return [value]
    return []


@function("timeOf")
def time_of(call: Call):
    value = call.input_value()
    if isinstance(value, FPDateTime):
        time = value.to_time()
        return [] if time is None else [time]
    return []


# --------------------------------------------------------------- precision

#: digits of each precision level for Date/DateTime and Time
_DATE_DIGITS = {
    YEAR: 4,
    MONTH: 6,
    DAY: 8,
    HOUR: 10,
    MINUTE: 12,
    SECOND: 14,
    MILLISECOND: 17,
}
_TIME_DIGITS = {HOUR: 2, MINUTE: 4, SECOND: 6, MILLISECOND: 9}


@function("precision")
def precision(call: Call):
    value = call.input_value()
    if value is MISSING:
        return []
    if isinstance(value, bool):
        return []
    if isinstance(value, Decimal):
        return [decimal_places(value)]
    if is_integer(value):
        return [0]
    if isinstance(value, FPTime):
        return [_TIME_DIGITS[value.precision]]
    if isinstance(value, (FPDate, FPDateTime)):
        return [_DATE_DIGITS[value.precision]]
    if isinstance(value, Quantity):
        return [decimal_places(value.value)]
    return []


def _decimal_boundary(
    value: Decimal, digits: Optional[int], high: bool
) -> Optional[Decimal]:
    if digits is None:
        digits = 8
    if digits < 0 or digits > 28:
        return None
    places = decimal_places(value)
    quantum = Decimal(1).scaleb(-digits)
    if digits < places:
        # coarser than the input: widen by half a unit of the target precision, truncate
        half = Decimal(5).scaleb(-(digits + 1))
        edge = value + half if high else value - half
        return edge.quantize(quantum, rounding=ROUND_DOWN)
    half = Decimal(5).scaleb(-(places + 1))
    edge = value + half if high else value - half
    if digits > places:
        return edge.quantize(quantum)
    return edge.quantize(quantum, rounding=ROUND_CEILING if high else ROUND_FLOOR)


def _temporal_boundary(value, digits: Optional[int], high: bool):
    table = _TIME_DIGITS if isinstance(value, FPTime) else _DATE_DIGITS
    if digits is None:
        digits = (
            9 if isinstance(value, FPTime) else (8 if isinstance(value, FPDate) else 17)
        )
    levels = [level for level, count in table.items() if count == digits]
    if not levels:
        return None
    target = levels[0]
    if isinstance(value, FPDate) and target > DAY:
        return None
    if isinstance(value, FPDateTime):
        if value.precision == HOUR:
            # hour-only times are not valid FHIR: read @...T08 as 08:00
            value = value.replace(minute=0, precision=MINUTE)
        if value.tz is None and target >= HOUR:
            # unknown offset: the earliest instant is at +14:00, the latest at -12:00
            value = value.replace(tz=-12 * 60 if high else 14 * 60)
    if target <= value.precision:
        fields = {"precision": target}
        for level, name in enumerate(
            ("year", "month", "day", "hour", "minute", "second", "millisecond")
        ):
            if level > target:
                fields[name] = None
        return value.replace(**fields)
    fields = {"precision": target}
    year = value.year
    month = value.month if value.month is not None else (12 if high else 1)
    for level, name in enumerate(
        ("year", "month", "day", "hour", "minute", "second", "millisecond")
    ):
        if level < value.LOW or level <= value.precision or level > target:
            continue
        if name == "month":
            fields[name] = month
        elif name == "day":
            fields[name] = days_in_month(year, month) if high else 1
        elif name == "hour":
            fields[name] = 23 if high else 0
        elif name in ("minute", "second"):
            fields[name] = 59 if high else 0
        else:
            fields[name] = 999 if high else 0
    if target >= SECOND and value.precision < SECOND:
        fields.setdefault("millisecond", 999 if high else 0)
        if target == SECOND:
            fields["millisecond"] = None
    return value.replace(**fields)


def _boundary(call: Call, high: bool):
    value = call.input_value()
    if value is MISSING:
        return []
    digits = call.arg_integer(0) if call.has_arg(0) else None
    if digits is MISSING:
        digits = None
    if isinstance(value, bool):
        return []
    if is_number(value):
        result = _decimal_boundary(as_decimal(value), digits, high)
        return [] if result is None else [result]
    if isinstance(value, Quantity):
        result = _decimal_boundary(value.value, digits, high)
        return [] if result is None else [Quantity(result, value.unit)]
    if isinstance(value, _TEMPORAL):
        result = _temporal_boundary(value, digits, high)
        return [] if result is None else [result]
    return []


@function("lowBoundary", 0, 1)
def low_boundary(call: Call):
    return _boundary(call, high=False)


@function("highBoundary", 0, 1)
def high_boundary(call: Call):
    return _boundary(call, high=True)


# ------------------------------------------------------- duration/difference

_PRECISIONS = {
    "year": YEAR,
    "month": MONTH,
    "week": DAY,
    "day": DAY,
    "hour": HOUR,
    "minute": MINUTE,
    "second": SECOND,
    "millisecond": MILLISECOND,
}


def _interval_args(call: Call):
    value = call.input_value()
    other = call.arg_value(0)
    unit = call.arg_string(1)
    if value is MISSING or other is MISSING or unit is MISSING:
        return None
    if isinstance(value, FPDate) and isinstance(other, FPDateTime):
        value = value.to_datetime_value()
    if isinstance(other, FPDate) and isinstance(value, FPDateTime):
        other = other.to_datetime_value()
    if not isinstance(value, _TEMPORAL) or type(value) is not type(other):
        raise call.error("arguments must be dates/times of the same type")
    if unit not in _PRECISIONS:
        raise call.error("invalid precision '%s'" % unit)
    level = _PRECISIONS[unit]
    if isinstance(value, FPTime) and level < HOUR:
        raise call.error("invalid precision '%s' for Time" % unit)
    if isinstance(value, FPDate) and level > DAY:
        raise call.error("invalid precision '%s' for Date" % unit)
    if value.precision < level or other.precision < level:
        return None
    if level >= HOUR and isinstance(value, FPDateTime):
        value, other = to_utc(value), to_utc(other)
    return value, other, unit


def _python(value) -> datetime.datetime:
    if isinstance(value, FPTime):
        return datetime.datetime(
            2000,
            1,
            1,
            value.hour,
            value.minute or 0,
            value.second or 0,
            (value.millisecond or 0) * 1000,
        )
    return value.to_datetime().replace(tzinfo=None)


def _months_between(a: datetime.datetime, b: datetime.datetime) -> int:
    sign = 1
    if b < a:
        a, b, sign = b, a, -1
    months = (b.year - a.year) * 12 + (b.month - a.month)
    if (b.day, b.time()) < (a.day, a.time()):
        months -= 1
    return sign * months


_UNIT_SECONDS = {
    "week": 604800,
    "day": 86400,
    "hour": 3600,
    "minute": 60,
    "second": 1,
    "millisecond": Decimal("0.001"),
}


@function("duration", 2)
def duration(call: Call):
    found = _interval_args(call)
    if found is None:
        return []
    start, end, unit = found
    a, b = _python(start), _python(end)
    if unit in ("year", "month"):
        months = _months_between(a, b)
        return [int(months / 12) if unit == "year" else months]
    delta = Decimal((b - a).total_seconds()).quantize(Decimal("0.001"))
    return [int(delta / Decimal(_UNIT_SECONDS[unit]))]


def _truncate(value: datetime.datetime, unit: str) -> datetime.datetime:
    if unit == "year":
        return value.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    if unit == "month":
        return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if unit == "week":
        day = value.replace(hour=0, minute=0, second=0, microsecond=0)
        return day - datetime.timedelta(
            days=(day.weekday() + 1) % 7
        )  # weeks start Sunday
    if unit == "day":
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    if unit == "hour":
        return value.replace(minute=0, second=0, microsecond=0)
    if unit == "minute":
        return value.replace(second=0, microsecond=0)
    if unit == "second":
        return value.replace(microsecond=0)
    return value


@function("difference", 2)
def difference(call: Call):
    found = _interval_args(call)
    if found is None:
        return []
    start, end, unit = found
    a, b = _truncate(_python(start), unit), _truncate(_python(end), unit)
    if unit == "year":
        return [b.year - a.year]
    if unit == "month":
        return [(b.year - a.year) * 12 + b.month - a.month]
    delta = Decimal((b - a).total_seconds()).quantize(Decimal("0.001"))
    return [int(delta / Decimal(_UNIT_SECONDS[unit]))]


# ---------------------------------------------------------------- comparable


@function("comparable", 1)
def comparable(call: Call):
    value = call.input_value()
    other = call.arg_value(0)
    if value is MISSING or other is MISSING:
        return []
    left, right = as_quantity(value), as_quantity(other)
    if left is None or right is None:
        return []
    return [quantity_ops.comparable(left, right)]


__all__: Any = []
