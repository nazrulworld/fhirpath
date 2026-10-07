# _*_ coding: utf-8 _*_
"""Quantity comparison, equivalence and arithmetic (calendar durations + UCUM)."""

from decimal import Decimal
from typing import Optional, Tuple

from .. import ucum
from ..types import Quantity

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

#: calendar duration -> UCUM unit with the same definite length
CALENDAR_TO_UCUM = {
    "week": "wk",
    "day": "d",
    "hour": "h",
    "minute": "min",
    "second": "s",
    "millisecond": "ms",
}
#: calendar durations in days (only year/month need this; used within the calendar system)
_CALENDAR_DAYS = {"year": Decimal(365), "month": Decimal(30)}
_CALENDAR_SECONDS = {
    "week": Decimal(604800),
    "day": Decimal(86400),
    "hour": Decimal(3600),
    "minute": Decimal(60),
    "second": Decimal(1),
    "millisecond": Decimal("0.001"),
}
_YEAR_MONTH = ("year", "month")
_UCUM_YEAR_MONTH = ("a", "mo", "a_j", "a_g", "a_t", "mo_j", "mo_g", "mo_s")


def _calendar_ratio(a: str, b: str) -> Tuple[Decimal, Decimal]:
    """(numerator, denominator) with value_in_b = value_in_a * numerator / denominator."""
    if a in _YEAR_MONTH and b in _YEAR_MONTH:
        return (Decimal(12), Decimal(1)) if a == "year" else (Decimal(1), Decimal(12))
    seconds_a = (
        _CALENDAR_DAYS[a] * 86400 if a in _CALENDAR_DAYS else _CALENDAR_SECONDS[a]
    )
    seconds_b = (
        _CALENDAR_DAYS[b] * 86400 if b in _CALENDAR_DAYS else _CALENDAR_SECONDS[b]
    )
    return seconds_a, seconds_b


def _granularity(unit: str, calendar: bool) -> Optional[Decimal]:
    """Size of one unit (seconds for calendar units, UCUM base factor otherwise)."""
    if calendar:
        if unit in _CALENDAR_DAYS:
            return _CALENDAR_DAYS[unit] * 86400
        return _CALENDAR_SECONDS[unit]
    if ucum.is_special(unit):
        return Decimal(1)
    try:
        return ucum.factor(unit)
    except (ucum.UcumError, ArithmeticError, ValueError):
        return None


def _map_units(
    left: Quantity, right: Quantity, equivalence: bool
) -> Optional[Tuple[str, str, bool]]:
    """Units of both operands in one system: ``(unit_left, unit_right, calendar?)``."""
    lu, ru = left.unit, right.unit
    lc, rc = left.is_calendar, right.is_calendar
    if lc and rc:
        return lu, ru, True
    if not lc and not rc:
        return lu, ru, False
    calendar_unit, ucum_unit = (lu, ru) if lc else (ru, lu)
    if calendar_unit in _YEAR_MONTH or ucum_unit in _UCUM_YEAR_MONTH:
        if not equivalence:
            return None
        mapped = (
            "a"
            if calendar_unit == "year"
            else ("mo" if calendar_unit == "month" else CALENDAR_TO_UCUM[calendar_unit])
        )
    else:
        mapped = CALENDAR_TO_UCUM[calendar_unit]
    return (mapped, ru, False) if lc else (lu, mapped, False)


def convert_value(
    value: Decimal, from_unit: str, to_unit: str, calendar: bool
) -> Optional[Decimal]:
    if from_unit == to_unit:
        return value
    if calendar:
        numerator, denominator = _calendar_ratio(from_unit, to_unit)
        return ucum.clean(value * numerator / denominator)
    return ucum.convert(value, from_unit, to_unit)


def common_values(
    left: Quantity,
    right: Quantity,
    equivalence: bool = False,
    most_granular: bool = False,
) -> Optional[Tuple[Decimal, Decimal, str, bool]]:
    """Both values expressed in one unit (least granular unless ``most_granular``)."""
    mapped = _map_units(left, right, equivalence)
    if mapped is None:
        return None
    lu, ru, calendar = mapped
    if lu == ru:
        return left.value, right.value, lu, calendar
    if not calendar and not ucum.commensurable(lu, ru):
        return None
    gl, gr = _granularity(lu, calendar), _granularity(ru, calendar)
    if gl is None or gr is None:
        return None
    if most_granular:
        target = lu if gl <= gr else ru
    else:
        target = lu if gl >= gr else ru
    lv = convert_value(left.value, lu, target, calendar)
    rv = convert_value(right.value, ru, target, calendar)
    if lv is None or rv is None:
        return None
    return lv, rv, target, calendar


def compare(left: Quantity, right: Quantity) -> Optional[int]:
    values = common_values(left, right)
    if values is None:
        return None
    lv, rv = values[0], values[1]
    return (lv > rv) - (lv < rv)


def equals(left: Quantity, right: Quantity) -> Optional[bool]:
    result = compare(left, right)
    return None if result is None else result == 0


def equivalent(left: Quantity, right: Quantity) -> bool:
    from .equality import decimal_equivalent

    values = common_values(left, right, equivalence=True)
    if values is None:
        return False
    return decimal_equivalent(values[0], values[1])


def comparable(left: Quantity, right: Quantity) -> bool:
    if left.is_calendar or right.is_calendar:
        return (
            _map_units(left, right, equivalence=False) is not None
            and common_values(left, right) is not None
        )
    return (
        ucum.is_valid(left.unit)
        and ucum.is_valid(right.unit)
        and ucum.commensurable(left.unit, right.unit)
    )


# ---------------------------------------------------------------------------
# arithmetic
# ---------------------------------------------------------------------------


def add(left: Quantity, right: Quantity, sign: int = 1) -> Optional[Quantity]:
    if left.unit == right.unit:
        return Quantity(left.value + sign * right.value, left.unit)
    if ucum.is_special(left.unit) or ucum.is_special(right.unit):
        return None
    lc, rc = left.is_calendar, right.is_calendar
    if lc != rc:
        # cross-system time units: result in calendar units
        calendar_unit = left.unit if lc else right.unit
        ucum_unit = right.unit if lc else left.unit
        if calendar_unit in _YEAR_MONTH or ucum_unit in _UCUM_YEAR_MONTH:
            return None
        reverse = {v: k for k, v in CALENDAR_TO_UCUM.items()}
        if ucum_unit not in reverse:
            return None
        if lc:
            right = Quantity(right.value, reverse[ucum_unit])
        else:
            left = Quantity(left.value, reverse[ucum_unit])
    elif lc and rc and (left.unit in _YEAR_MONTH or right.unit in _YEAR_MONTH):
        # year/month durations are not definite: no implicit conversion in arithmetic
        return None
    values = common_values(left, right, most_granular=True)
    if values is None:
        return None
    lv, rv, unit, _ = values
    return Quantity(lv + sign * rv, unit)


def multiply(
    left: Quantity, right: Quantity, divide: bool = False
) -> Optional[Quantity]:
    for quantity in (left, right):
        if quantity.is_calendar or ucum.is_special(quantity.unit):
            return None
    if divide and right.value == 0:
        return None
    unit = ucum.multiply_units(left.unit, right.unit, -1 if divide else 1)
    if unit is None:
        return None
    value = left.value / right.value if divide else left.value * right.value
    # simplify units that cancel to a pure number (e.g. 'cm/m')
    try:
        parsed = ucum.parse(unit)
        if not parsed.dims and unit != "1":
            value = value * parsed.factor
            unit = "1"
    except (ucum.UcumError, ArithmeticError, ValueError):
        pass
    return Quantity(value, unit)


__all__ = [
    "compare",
    "equals",
    "equivalent",
    "comparable",
    "add",
    "multiply",
    "common_values",
]
