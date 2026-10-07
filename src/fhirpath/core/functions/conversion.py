# _*_ coding: utf-8 _*_
"""Conversion functions (``iif``, ``toX()``, ``convertsToX()``)."""

import re
from decimal import Decimal
from typing import Any, Optional

from .. import ucum
from ..operators.quantity import CALENDAR_TO_UCUM, convert_value
from ..types import (
    CALENDAR_UNITS,
    INTEGER_MAX,
    INTEGER_MIN,
    LONG_MAX,
    LONG_MIN,
    FPDate,
    FPDateTime,
    FPTime,
    Long,
    Quantity,
    format_decimal,
)
from ..values import MISSING, is_integer, singleton_boolean
from .registry import Call, function

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_DECIMAL_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")
_QUANTITY_RE = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*(?:'([^']+)'|([a-zA-Z]+))?\s*$")
_TRUE = {"true", "t", "yes", "y", "1", "1.0"}
_FALSE = {"false", "f", "no", "n", "0", "0.0"}

#: sentinel: conversion not possible
FAIL = object()


@function("iif", 2, 3)
def iif(call: Call):
    if len(call.input) > 1:
        raise call.error("input must contain at most one item")
    ctx = call.ctx.derive(this=call.input)  # iif does not set $index

    criterion = singleton_boolean(
        call.engine.evaluate(call.args[0], ctx), "criterion of iif()"
    )
    if criterion is True:
        return call.engine.evaluate(call.args[1], ctx)
    if len(call.args) > 2:
        return call.engine.evaluate(call.args[2], ctx)
    return []


# ---------------------------------------------------------------- converters


def to_boolean(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if is_integer(value):
        return {1: True, 0: False}.get(int(value), FAIL)
    if isinstance(value, Decimal):
        if value == 1:
            return True
        if value == 0:
            return False
        return FAIL
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
    return FAIL


def to_integer(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    if is_integer(value):
        return int(value) if INTEGER_MIN <= value <= INTEGER_MAX else FAIL
    if isinstance(value, str) and _INTEGER_RE.match(value):
        number = int(value)
        return number if INTEGER_MIN <= number <= INTEGER_MAX else FAIL
    return FAIL


def to_long(value: Any) -> Any:
    if isinstance(value, bool):
        return Long(1 if value else 0)
    if is_integer(value):
        return Long(value)
    if isinstance(value, str) and _INTEGER_RE.match(value):
        number = int(value)
        return Long(number) if LONG_MIN <= number <= LONG_MAX else FAIL
    return FAIL


def to_decimal(value: Any) -> Any:
    if isinstance(value, bool):
        return Decimal("1.0") if value else Decimal("0.0")
    if is_integer(value):
        return Decimal(int(value))
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str) and _DECIMAL_RE.match(value):
        return Decimal(value)
    return FAIL


def to_date(value: Any, fmt: Optional[str] = None) -> Any:
    if isinstance(value, FPDateTime):
        return value.to_date()
    if isinstance(value, FPDate):
        return value
    if isinstance(value, str):
        if fmt is not None:
            parsed = parse_with_format(value, fmt)
            return parsed.to_date() if parsed is not None else FAIL
        parsed = FPDate.parse(value)
        if parsed is None:
            datetime_value = FPDateTime.parse(value)
            parsed = datetime_value.to_date() if datetime_value is not None else None
        return FAIL if parsed is None else parsed
    return FAIL


def to_datetime(value: Any, fmt: Optional[str] = None) -> Any:
    if isinstance(value, FPDateTime):
        return value
    if isinstance(value, FPDate):
        return value.to_datetime_value()
    if isinstance(value, str):
        if fmt is not None:
            parsed = parse_with_format(value, fmt)
            return parsed if parsed is not None else FAIL
        parsed = FPDateTime.parse(value)
        return FAIL if parsed is None else parsed
    return FAIL


def to_time(value: Any) -> Any:
    if isinstance(value, FPTime):
        return value
    if isinstance(value, str):
        parsed = FPTime.parse(value[1:] if value.startswith("T") else value)
        return FAIL if parsed is None else parsed
    return FAIL


def to_quantity(value: Any, unit: Optional[str] = None) -> Any:
    if isinstance(value, bool):
        quantity = Quantity(Decimal("1.0") if value else Decimal("0.0"), "1")
    elif is_integer(value) or isinstance(value, Decimal):
        quantity = Quantity(Decimal(value), "1")
    elif isinstance(value, Quantity):
        quantity = value
    elif isinstance(value, str):
        match = _QUANTITY_RE.match(value)
        if not match:
            return FAIL
        number, quoted, word = match.groups()
        if word is not None:
            if word not in CALENDAR_UNITS:
                return FAIL
            unit_text = CALENDAR_UNITS[word]
        else:
            unit_text = quoted if quoted is not None else "1"
            if not ucum.is_valid(unit_text):
                return FAIL
        quantity = Quantity(Decimal(number), unit_text)
    else:
        return FAIL
    if unit is None:
        return quantity
    converted = convert_quantity(quantity, unit)
    return FAIL if converted is None else converted


_UCUM_TO_CALENDAR = {
    "a": "year",
    "mo": "month",
    **{v: k for k, v in CALENDAR_TO_UCUM.items()},
}
_CALENDAR_TO_UCUM_ALL = {"year": "a", "month": "mo", **CALENDAR_TO_UCUM}


def convert_quantity(quantity: Quantity, unit: str) -> Optional[Quantity]:
    """Explicit conversion: convert inside the source system, then relabel."""
    target = CALENDAR_UNITS.get(unit, unit)
    if quantity.unit == target:
        return quantity
    target_calendar = target in CALENDAR_UNITS.values()
    if quantity.is_calendar == target_calendar:
        value = convert_value(
            quantity.value, quantity.unit, target, quantity.is_calendar
        )
        return None if value is None else Quantity(value, target)
    if quantity.is_calendar:
        source_target = _UCUM_TO_CALENDAR.get(target)
    else:
        source_target = _CALENDAR_TO_UCUM_ALL.get(target)
    if source_target is None:
        return None
    value = convert_value(
        quantity.value, quantity.unit, source_target, quantity.is_calendar
    )
    return None if value is None else Quantity(value, target)


def to_string(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if is_integer(value):
        return str(int(value))
    if isinstance(value, Decimal):
        return format_decimal(value)
    if isinstance(value, (FPDate, FPDateTime, FPTime)):
        return value.isoformat()
    if isinstance(value, Quantity):
        return str(value)
    return FAIL


# ------------------------------------------------------------ date formats

_FORMAT_TOKENS = re.compile(r"yyyy|yy|MMMM|MMM|MM|M|dd|d|HH|H|hh|h|mm|m|ss|s|S+|a|Z|z")
_MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]


def parse_with_format(text: str, fmt: str) -> Optional[FPDateTime]:
    """Parse ``text`` with a FHIRPath date format (``yyyy MM dd HH mm ss SSS a Z``)."""
    pattern = ""
    fields = []
    pos = 0
    for match in _FORMAT_TOKENS.finditer(fmt):
        pattern += re.escape(fmt[pos : match.start()])
        token = match.group(0)
        if token == "yyyy":
            pattern += r"(\d{4})"
        elif token in ("yy", "MM", "dd", "HH", "hh", "mm", "ss"):
            pattern += r"(\d{2})"
        elif token in ("M", "d", "H", "h", "m", "s"):
            pattern += r"(\d{1,2})"
        elif token in ("MMM", "MMMM"):
            pattern += r"([A-Za-z]+)"
        elif token.startswith("S"):
            pattern += r"(\d{%d,})" % len(token)
        elif token == "a":
            pattern += r"([AaPp][Mm])"
        else:  # Z / z
            pattern += r"(Z|[+-]\d{2}:?\d{2})"
        fields.append(token)
        pos = match.end()
    pattern += re.escape(fmt[pos:])
    found = re.fullmatch(pattern, text)
    if not found:
        return None
    parts = dict(
        year=None,
        month=None,
        day=None,
        hour=None,
        minute=None,
        second=None,
        millisecond=None,
    )
    tz = None
    meridiem = None
    for token, value in zip(fields, found.groups()):
        if token == "yyyy":
            parts["year"] = int(value)
        elif token == "yy":
            parts["year"] = 2000 + int(value)
        elif token in ("MM", "M"):
            parts["month"] = int(value)
        elif token in ("MMM", "MMMM"):
            names = [m for m in _MONTHS if m.startswith(value.lower())]
            if len(names) != 1:
                return None
            parts["month"] = _MONTHS.index(names[0]) + 1
        elif token in ("dd", "d"):
            parts["day"] = int(value)
        elif token in ("HH", "H", "hh", "h"):
            parts["hour"] = int(value)
        elif token in ("mm", "m"):
            parts["minute"] = int(value)
        elif token in ("ss", "s"):
            parts["second"] = int(value)
        elif token.startswith("S"):
            parts["millisecond"] = int((value + "00")[:3])
        elif token == "a":
            meridiem = value.lower()
        else:
            tz = (
                0
                if value == "Z"
                else (1 if value[0] == "+" else -1)
                * (int(value[1:3]) * 60 + int(value[-2:]))
            )
    if meridiem and parts["hour"] is not None:
        parts["hour"] = parts["hour"] % 12 + (12 if meridiem == "pm" else 0)
    precision = -1
    for level, name in enumerate(
        ("year", "month", "day", "hour", "minute", "second", "millisecond")
    ):
        if parts[name] is None:
            break
        precision = level
    if precision < 0:
        return None
    text_value = "%04d" % parts["year"]
    if precision >= 1:
        text_value += "-%02d" % parts["month"]
    if precision >= 2:
        text_value += "-%02d" % parts["day"]
    if precision >= 3:
        text_value += "T%02d" % parts["hour"]
        if precision >= 4:
            text_value += ":%02d" % parts["minute"]
        if precision >= 5:
            text_value += ":%02d" % parts["second"]
        if precision >= 6:
            text_value += ".%03d" % parts["millisecond"]
    value = FPDateTime.parse(text_value)
    if value is not None and tz is not None and precision >= 3:
        value = value.replace(tz=tz)
    return value


# ------------------------------------------------------------ registrations


def _register(name: str, converter, with_arg: Optional[str] = None):
    def to_function(call: Call):
        value = call.input_value()
        if value is MISSING:
            return []
        extra = _extra_arg(call, with_arg)
        if extra is MISSING:
            return []
        result = converter(value) if extra is None else converter(value, extra)
        return [] if result is FAIL else [result]

    def converts_function(call: Call):
        value = call.input_value()
        if value is MISSING:
            return []
        extra = _extra_arg(call, with_arg)
        if extra is MISSING:
            return []
        result = converter(value) if extra is None else converter(value, extra)
        return [result is not FAIL]

    max_args = 1 if with_arg else 0
    function("to" + name, 0, max_args)(to_function)
    function("convertsTo" + name, 0, max_args)(converts_function)


def _extra_arg(call: Call, with_arg: Optional[str]):
    if not with_arg or not call.has_arg(0):
        return None
    return call.arg_string(0)


_register("Boolean", to_boolean)
_register("Integer", to_integer)
_register("Long", to_long)
_register("Decimal", to_decimal)
_register("Date", to_date, "format")
_register("DateTime", to_datetime, "format")
_register("Time", to_time)
_register("Quantity", to_quantity, "unit")
_register("String", to_string)


__all__ = [
    "to_boolean",
    "to_integer",
    "to_long",
    "to_decimal",
    "to_date",
    "to_datetime",
    "to_time",
    "to_quantity",
    "to_string",
    "convert_quantity",
    "FAIL",
]
