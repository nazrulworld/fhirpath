# _*_ coding: utf-8 _*_
"""FHIRPath System types that have no direct Python equivalent.

Mapping of System types to Python values used by the engine:

=================  ==========================================
System.Boolean     ``bool``
System.String      ``str``
System.Integer     ``int`` (never ``bool``)
System.Long        :class:`Long` (``int`` subclass)
System.Decimal     ``decimal.Decimal`` (never ``float``)
System.Date        :class:`FPDate`
System.DateTime    :class:`FPDateTime`
System.Time        :class:`FPTime`
System.Quantity    :class:`Quantity`
=================  ==========================================
"""

import calendar
import datetime
import re
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Optional, Tuple

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

INTEGER_MIN, INTEGER_MAX = -(2**31), 2**31 - 1
LONG_MIN, LONG_MAX = -(2**63), 2**63 - 1


class Long(int):
    """System.Long (64-bit integer, literal ``42L``)."""

    def __repr__(self):
        return "Long(%d)" % int(self)


# ---------------------------------------------------------------------------
# Date / DateTime / Time with partial precision
# ---------------------------------------------------------------------------

YEAR, MONTH, DAY, HOUR, MINUTE, SECOND, MILLISECOND = range(7)
PRECISION_NAMES = ("year", "month", "day", "hour", "minute", "second", "millisecond")
_FIELDS = PRECISION_NAMES

_DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")
_TIME_RE = re.compile(r"^(\d{2})(?::(\d{2})(?::(\d{2})(?:\.(\d+))?)?)?$")
_TZ_RE = re.compile(r"(Z|[+-]\d{2}:\d{2})$")


def _parse_tz(text: str) -> Optional[int]:
    """Offset in minutes; ``None`` when absent."""
    if text == "Z":
        return 0
    sign = -1 if text[0] == "-" else 1
    return sign * (int(text[1:3]) * 60 + int(text[4:6]))


def _format_tz(offset: Optional[int]) -> str:
    if offset is None:
        return ""
    if offset == 0:
        return "Z"
    sign = "-" if offset < 0 else "+"
    offset = abs(offset)
    return "%s%02d:%02d" % (sign, offset // 60, offset % 60)


def _ms_from_fraction(fraction: str) -> int:
    return int((fraction + "000")[:3])


class _Temporal:
    """Common base: components ``year … millisecond`` plus precision and offset."""

    __slots__ = (
        "year",
        "month",
        "day",
        "hour",
        "minute",
        "second",
        "millisecond",
        "precision",
        "tz",
    )
    #: lowest precision index this kind can hold
    LOW = YEAR
    #: highest precision index this kind can hold
    HIGH = MILLISECOND

    def __init__(
        self,
        year=None,
        month=None,
        day=None,
        hour=None,
        minute=None,
        second=None,
        millisecond=None,
        precision=None,
        tz=None,
    ):
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self.millisecond = millisecond
        self.precision = precision
        self.tz = tz

    # -- helpers -----------------------------------------------------------
    def components(self) -> Tuple:
        return tuple(getattr(self, f) for f in _FIELDS)

    def replace(self, **kwargs):
        values = {f: getattr(self, f) for f in _Temporal.__slots__}
        values.update(kwargs)
        return self.__class__(**values)

    def _key(self):
        return (
            (self.__class__.__name__,) + self.components() + (self.precision, self.tz)
        )

    def __hash__(self):
        return hash(self._key())

    def __eq__(self, other):
        # structural identity only (used for hashing/dedup in Python containers);
        # FHIRPath equality lives in operators.equality.
        return isinstance(other, _Temporal) and self._key() == other._key()

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.isoformat())

    def __str__(self):
        return self.isoformat()

    def _time_part(self) -> str:
        text = "%02d" % self.hour
        if self.precision >= MINUTE:
            text += ":%02d" % self.minute
        if self.precision >= SECOND:
            text += ":%02d" % self.second
        if self.precision >= MILLISECOND:
            text += ".%03d" % self.millisecond
        return text

    def _date_part(self) -> str:
        text = "%04d" % self.year
        if self.precision >= MONTH:
            text += "-%02d" % self.month
        if self.precision >= DAY:
            text += "-%02d" % self.day
        return text

    def to_datetime(self) -> datetime.datetime:
        """Full-precision Python datetime, missing components filled with their minimum."""
        tzinfo = None
        if self.tz is not None:
            tzinfo = datetime.timezone(datetime.timedelta(minutes=self.tz))
        return datetime.datetime(
            self.year or 1,
            self.month or 1,
            self.day or 1,
            self.hour or 0,
            self.minute or 0,
            self.second or 0,
            (self.millisecond or 0) * 1000,
            tzinfo=tzinfo,
        )


class FPDate(_Temporal):
    """System.Date: ``@2014``, ``@2014-01``, ``@2014-01-25``."""

    __slots__ = ()
    HIGH = DAY

    @classmethod
    def parse(cls, text: str) -> Optional["FPDate"]:
        match = _DATE_RE.match(text)
        if not match:
            return None
        year, month, day = match.groups()
        try:
            value = cls(
                int(year),
                int(month) if month else None,
                int(day) if day else None,
                precision=DAY if day else (MONTH if month else YEAR),
            )
            value.validate()
        except ValueError:
            return None
        return value

    @classmethod
    def from_python(cls, value: datetime.date) -> "FPDate":
        return cls(value.year, value.month, value.day, precision=DAY)

    def validate(self):
        if self.year < 1:
            raise ValueError("year out of range")
        if self.precision >= MONTH and not 1 <= self.month <= 12:
            raise ValueError("month out of range")
        if self.precision >= DAY:
            datetime.date(self.year, self.month, self.day)

    def isoformat(self) -> str:
        return self._date_part()

    def to_datetime_value(self) -> "FPDateTime":
        return FPDateTime(self.year, self.month, self.day, precision=self.precision)


class FPDateTime(_Temporal):
    """System.DateTime: ``@2014T`` … ``@2014-01-25T14:30:14.559+10:00``."""

    __slots__ = ()

    @classmethod
    def parse(cls, text: str) -> Optional["FPDateTime"]:
        if "T" in text:
            date_text, time_text = text.split("T", 1)
        else:
            date_text, time_text = text, ""
        date = FPDate.parse(date_text)
        if date is None:
            return None
        value = cls(date.year, date.month, date.day, precision=date.precision)
        if not time_text:
            return value
        if date.precision != DAY:
            return None
        tz = None
        tz_match = _TZ_RE.search(time_text)
        if tz_match:
            tz = _parse_tz(tz_match.group(1))
            time_text = time_text[: tz_match.start()]
        time = FPTime.parse(time_text)
        if time is None:
            return None
        return value.replace(
            hour=time.hour,
            minute=time.minute,
            second=time.second,
            millisecond=time.millisecond,
            precision=time.precision,
            tz=tz,
        )

    @classmethod
    def from_python(cls, value: datetime.datetime) -> "FPDateTime":
        tz = None
        if value.utcoffset() is not None:
            tz = int(value.utcoffset().total_seconds() // 60)
        precision = MILLISECOND if value.microsecond else SECOND
        return cls(
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            value.microsecond // 1000,
            precision=precision,
            tz=tz,
        )

    def isoformat(self) -> str:
        text = self._date_part()
        if self.precision >= HOUR:
            text += "T" + self._time_part() + _format_tz(self.tz)
        return text

    def literal(self) -> str:
        """FHIRPath literal form (partial dates keep the trailing ``T``)."""
        text = self.isoformat()
        return "@" + text + ("T" if self.precision < HOUR else "")

    def to_date(self) -> FPDate:
        return FPDate(
            self.year, self.month, self.day, precision=min(self.precision, DAY)
        )

    def to_time(self) -> Optional["FPTime"]:
        if self.precision < HOUR:
            return None
        return FPTime(
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            millisecond=self.millisecond,
            precision=self.precision,
        )


class FPTime(_Temporal):
    """System.Time: ``@T14``, ``@T14:30``, ``@T14:30:14.559`` (no offset)."""

    __slots__ = ()
    LOW = HOUR

    @classmethod
    def parse(cls, text: str) -> Optional["FPTime"]:
        match = _TIME_RE.match(text)
        if not match:
            return None
        hour, minute, second, fraction = match.groups()
        if fraction is not None:
            precision = MILLISECOND
        elif second is not None:
            precision = SECOND
        elif minute is not None:
            precision = MINUTE
        else:
            precision = HOUR
        value = cls(
            hour=int(hour),
            minute=int(minute) if minute else None,
            second=int(second) if second else None,
            millisecond=_ms_from_fraction(fraction) if fraction else None,
            precision=precision,
        )
        if (
            value.hour > 23
            or (value.minute is not None and value.minute > 59)
            or (value.second is not None and value.second > 59)
        ):
            return None
        return value

    @classmethod
    def from_python(cls, value: datetime.time) -> "FPTime":
        return cls(
            hour=value.hour,
            minute=value.minute,
            second=value.second,
            millisecond=value.microsecond // 1000,
            precision=MILLISECOND if value.microsecond else SECOND,
        )

    def isoformat(self) -> str:
        return self._time_part()


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


# ---------------------------------------------------------------------------
# Quantity
# ---------------------------------------------------------------------------

CALENDAR_UNITS = {
    "year": "year",
    "years": "year",
    "month": "month",
    "months": "month",
    "week": "week",
    "weeks": "week",
    "day": "day",
    "days": "day",
    "hour": "hour",
    "hours": "hour",
    "minute": "minute",
    "minutes": "minute",
    "second": "second",
    "seconds": "second",
    "millisecond": "millisecond",
    "milliseconds": "millisecond",
}


class Quantity:
    """System.Quantity: a Decimal value with a UCUM unit or a calendar keyword.

    Calendar keywords are stored in their singular form (``year``, ``day``, …).
    """

    __slots__ = ("value", "unit")

    def __init__(self, value: Any, unit: Optional[str] = "1"):
        if not isinstance(value, Decimal):
            value = Decimal(value)
        self.value = value
        self.unit = CALENDAR_UNITS.get(unit, unit) if unit else "1"

    @property
    def code(self):
        return self.unit

    @property
    def is_calendar(self) -> bool:
        return self.unit in CALENDAR_UNITS

    def __repr__(self):
        return "Quantity(%s)" % self

    def __str__(self):
        value = format_decimal(self.value)
        if self.is_calendar:
            plural = "" if abs(self.value) == 1 else "s"
            return "%s %s%s" % (value, self.unit, plural)
        return "%s '%s'" % (value, self.unit)

    def __hash__(self):
        return hash((self.value.normalize(), self.unit))

    def __eq__(self, other):
        return (
            isinstance(other, Quantity)
            and self.value == other.value
            and self.unit == other.unit
        )


# ---------------------------------------------------------------------------
# Decimal helpers
# ---------------------------------------------------------------------------


def decimal_places(value: Decimal) -> int:
    """Digits after the decimal point as written (trailing zeros count)."""
    exponent = value.as_tuple().exponent
    return -exponent if isinstance(exponent, int) and exponent < 0 else 0


def significant_places(value: Decimal) -> int:
    """Digits after the decimal point ignoring trailing zeros."""
    if value == value.to_integral_value():
        return 0
    return decimal_places(value.normalize())


def format_decimal(value: Decimal) -> str:
    """Plain (non-exponent) rendering that keeps the written scale."""
    if not isinstance(value, Decimal):
        value = Decimal(value)
    text = format(value, "f")
    if text in ("-0",):
        return "0"
    return text


def round_half_away(value: Decimal, places: int) -> Decimal:
    """Round half away from zero (``ROUND_HALF_UP`` in :mod:`decimal` terms)."""
    try:
        return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return value


def truncate_decimal(value: Decimal) -> int:
    return int(value)


def floor_decimal(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


# ---------------------------------------------------------------------------
# Reflection (type()) results
# ---------------------------------------------------------------------------


class TypeInfo:
    """``SimpleTypeInfo`` / ``ClassInfo`` returned by ``type()``.

    Exposed to expressions as an object with ``namespace``, ``name`` and
    ``baseType`` children.
    """

    __slots__ = ("kind", "namespace", "name", "baseType")

    def __init__(self, kind: str, namespace: str, name: str, base_type: Optional[str]):
        self.kind = kind
        self.namespace = namespace
        self.name = name
        self.baseType = base_type

    def __repr__(self):
        return "%s(%s.%s)" % (self.kind, self.namespace, self.name)

    def __eq__(self, other):
        return isinstance(other, TypeInfo) and (
            self.kind,
            self.namespace,
            self.name,
            self.baseType,
        ) == (other.kind, other.namespace, other.name, other.baseType)

    def __hash__(self):
        return hash((self.kind, self.namespace, self.name))


class TypeSpecifier:
    """Parsed type specifier (``Quantity``, ``FHIR.Patient``, ``System.String``)."""

    __slots__ = ("namespace", "name")

    def __init__(self, namespace: Optional[str], name: str):
        self.namespace = namespace
        self.name = name

    def __repr__(self):
        return "TypeSpecifier(%s)" % self

    def __str__(self):
        return "%s.%s" % (self.namespace, self.name) if self.namespace else self.name

    def __eq__(self, other):
        return isinstance(other, TypeSpecifier) and (self.namespace, self.name) == (
            other.namespace,
            other.name,
        )

    def __hash__(self):
        return hash((self.namespace, self.name))


__all__ = [
    "Long",
    "FPDate",
    "FPDateTime",
    "FPTime",
    "Quantity",
    "TypeInfo",
    "TypeSpecifier",
    "CALENDAR_UNITS",
    "PRECISION_NAMES",
]
