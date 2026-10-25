# _*_ coding: utf-8 _*_
"""Implicit ranges of number and date search values (FHIR search §3.2.1.5.2).

Every search value stands for a range implied by its precision: ``100`` is
``[99.5, 100.5)``, ``100.00`` is ``[99.995, 100.005)``, ``1e2`` is ``[50, 150)``;
``2013`` is the whole year, ``2013-01`` the whole month, ``2013-01-14T10:00``
the whole minute. ``ap`` widens the range by 10 % of the value (numbers) or of
the gap between now and the date (dates).
"""
import calendar
import datetime
import math
import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

from fhirpath.search.exceptions import ValidationError

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

NUMBER_TYPES = ("integer", "decimal", "unsignedInt", "positiveInt", "integer64")
INTEGER_TYPES = ("integer", "unsignedInt", "positiveInt", "integer64")
DATE_TYPES = ("date", "dateTime", "instant")
APPROXIMATION = Decimal("0.1")

DATE_PATTERN = re.compile(
    r"^(?P<year>\d{4})"
    r"(?:-(?P<month>\d{2})"
    r"(?:-(?P<day>\d{2})"
    r"(?:T(?P<hour>\d{2}):(?P<minute>\d{2})"
    r"(?::(?P<second>\d{2})(?:\.(?P<fraction>\d+))?)?"
    r"(?P<tz>Z|[+-]\d{2}:\d{2})?"
    r")?)?)?$"
)


# -------------------------------------------------------------------- numbers


def parse_number(value: str) -> Decimal:
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValidationError(f"``{value}`` is not a valid number.")
    if not number.is_finite():
        raise ValidationError(f"``{value}`` is not a valid number.")
    return number


def number_range(value: str) -> Tuple[Decimal, Decimal]:
    """``[low, high)`` implied by the significant figures of ``value``."""
    number = parse_number(value)
    exponent = number.as_tuple().exponent
    half = Decimal(5).scaleb(exponent - 1)
    return number - half, number + half


def approximate_number_range(value: str) -> Tuple[Decimal, Decimal]:
    """``[low, high]`` of ``ap``: 10 % of the value (at least its precision)."""
    number = parse_number(value)
    low, high = number_range(value)
    tolerance = abs(number) * APPROXIMATION
    return min(low, number - tolerance), max(high, number + tolerance)


def _integer_bounds(low: Decimal, high: Decimal, high_inclusive: bool):
    """The same range on an integer element: ``[99.5, 100.5)`` -> ``[100, 101)``."""
    low_int = math.ceil(low)
    if high_inclusive:
        high_int = math.floor(high) + 1
    else:
        high_int = math.ceil(high)
    return str(low_int), str(high_int), False


def number_bounds(value: str, prefix: str, element_type: str):
    """``(low, high, high_inclusive)`` for ``eq``/``ne``/``ap`` on a number
    element, as strings valid for ``element_type``."""
    if prefix == "ap":
        low, high = approximate_number_range(value)
        high_inclusive = True
    else:
        low, high = number_range(value)
        high_inclusive = False
    if element_type in INTEGER_TYPES:
        return _integer_bounds(low, high, high_inclusive)
    return _plain(low), _plain(high), high_inclusive


def _plain(number: Decimal) -> str:
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


# ---------------------------------------------------------------------- dates


def _timezone(text: Optional[str]) -> Optional[datetime.tzinfo]:
    if not text:
        return None
    if text == "Z":
        return datetime.timezone.utc
    sign = 1 if text[0] == "+" else -1
    hours, minutes = text[1:].split(":")
    return datetime.timezone(
        sign * datetime.timedelta(hours=int(hours), minutes=int(minutes))
    )


def date_range(value: str) -> Tuple[datetime.datetime, datetime.datetime, str]:
    """``[low, high)`` of a (partial) date and its precision
    (``year`` ``month`` ``day`` ``minute`` ``second`` ``fraction``)."""
    match = DATE_PATTERN.match(value)
    if match is None:
        raise ValidationError(
            f"``{value}`` is not a valid search date (yyyy-mm-ddThh:mm:ss[Z|±hh:mm])."
        )
    parts = match.groupdict()
    tz = _timezone(parts["tz"])
    year = int(parts["year"])
    month = int(parts["month"] or 1)
    day = int(parts["day"] or 1)
    hour = int(parts["hour"] or 0)
    minute = int(parts["minute"] or 0)
    second = int(parts["second"] or 0)
    fraction = parts["fraction"] or ""
    microsecond = int((fraction + "000000")[:6]) if fraction else 0
    try:
        low = datetime.datetime(
            year, month, day, hour, minute, second, microsecond, tzinfo=tz
        )
    except ValueError as exc:
        raise ValidationError(f"``{value}`` is not a valid search date: {exc}")

    if parts["month"] is None:
        precision = "year"
        high = low.replace(year=year + 1)
    elif parts["day"] is None:
        precision = "month"
        high = low + datetime.timedelta(days=calendar.monthrange(year, month)[1])
    elif parts["hour"] is None:
        precision = "day"
        high = low + datetime.timedelta(days=1)
    elif parts["second"] is None:
        precision = "minute"
        high = low + datetime.timedelta(minutes=1)
    elif not fraction:
        precision = "second"
        high = low + datetime.timedelta(seconds=1)
    else:
        precision = "fraction"
        high = low + datetime.timedelta(
            microseconds=max(1, 10 ** (6 - min(len(fraction), 6)))
        )
    return low, high, precision


def _now(reference: datetime.datetime) -> datetime.datetime:
    if reference.tzinfo is not None:
        return datetime.datetime.now(tz=reference.tzinfo)
    return datetime.datetime.now()


def approximate_date_range(value: str):
    """``[low, high]`` of ``ap``: the value's range widened by 10 % of the gap
    between now and the date."""
    low, high, precision = date_range(value)
    gap = abs(_now(low) - low)
    tolerance = gap * 0.1
    return low - tolerance, high + tolerance, precision


def format_date_bound(
    moment: datetime.datetime, element_type: str, precision: str, upper: bool
) -> str:
    """A bound as a value of ``element_type``: day precision without time zone
    stays a date (the server's local day); ``date`` elements get dates only (an
    exclusive upper bound inside a day moves to the next day)."""
    if element_type == "date":
        day = moment.date()
        if upper and moment.time() != datetime.time(0, 0):
            day += datetime.timedelta(days=1)
        return day.isoformat()
    if (
        precision in ("year", "month", "day")
        and moment.tzinfo is None
        and moment.time() == datetime.time(0, 0)
    ):
        return moment.date().isoformat()
    if moment.microsecond:
        return moment.isoformat(timespec="microseconds")
    return moment.isoformat(timespec="seconds")


def date_bound(value: str, element_type: str, which: str) -> str:
    """``low`` or ``high`` (exclusive) bound of the range of ``value``."""
    low, high, precision = date_range(value)
    if which == "low":
        return format_date_bound(low, element_type, precision, upper=False)
    return format_date_bound(high, element_type, precision, upper=True)


def date_bounds(value: str, prefix: str, element_type: str):
    """``(low, high, high_inclusive)`` for ``eq``/``ne``/``ap`` on a date."""
    if prefix == "ap":
        low, high, precision = approximate_date_range(value)
        return (
            format_date_bound(low, element_type, "second", upper=False),
            format_date_bound(high, element_type, "second", upper=True),
            element_type != "date",
        )
    low, high, precision = date_range(value)
    return (
        format_date_bound(low, element_type, precision, upper=False),
        format_date_bound(high, element_type, precision, upper=True),
        False,
    )


# prefix -> (bound of the value's range, operator on the element) for the
# ordered date comparisons; a resource value is a point in time
DATE_PREFIX_BOUNDS = {
    "gt": ("high", "ge"),
    "ge": ("low", "ge"),
    "lt": ("low", "lt"),
    "le": ("high", "lt"),
    "sa": ("high", "ge"),
    "eb": ("low", "lt"),
}
