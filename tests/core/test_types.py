# _*_ coding: utf-8 _*_
"""System types (partial temporals, Quantity) and the built-in UCUM subset."""

import datetime
from decimal import Decimal

import pytest

from fhirpath.core import ucum
from fhirpath.core.types import (
    DAY,
    MILLISECOND,
    MINUTE,
    MONTH,
    YEAR,
    FPDate,
    FPDateTime,
    FPTime,
    Quantity,
    decimal_places,
    format_decimal,
    round_half_away,
    significant_places,
)

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


@pytest.mark.parametrize(
    "text,precision",
    [("2014", YEAR), ("2014-01", MONTH), ("2014-01-25", DAY)],
)
def test_date_parse_precision(text, precision):
    value = FPDate.parse(text)
    assert value.precision == precision
    assert value.isoformat() == text


@pytest.mark.parametrize(
    "text", ["2014-13", "2014-02-30", "14-01-01", "2014-1-1", "0000"]
)
def test_date_parse_invalid(text):
    assert FPDate.parse(text) is None


def test_datetime_parse_and_format():
    value = FPDateTime.parse("2014-01-25T14:30:14.559+10:00")
    assert value.precision == MILLISECOND and value.tz == 600
    assert value.isoformat() == "2014-01-25T14:30:14.559+10:00"
    assert FPDateTime.parse("2014-01-25T14:30Z").isoformat() == "2014-01-25T14:30Z"
    assert FPDateTime.parse("2014").literal() == "@2014T"
    assert FPDateTime.parse("2014-01T10:00") is None
    assert FPDateTime.parse("2014-01-25T14:30").precision == MINUTE


def test_time_parse():
    assert FPTime.parse("14:30:14.5").millisecond == 500
    assert FPTime.parse("24:00") is None
    assert FPTime.parse("14:30").isoformat() == "14:30"


def test_from_python():
    assert FPDate.from_python(datetime.date(2020, 1, 2)).isoformat() == "2020-01-02"
    aware = datetime.datetime(
        2020, 1, 2, 3, 4, 5, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))
    )
    assert FPDateTime.from_python(aware).isoformat() == "2020-01-02T03:04:05-05:00"
    assert (
        FPTime.from_python(datetime.time(1, 2, 3, 4000)).isoformat() == "01:02:03.004"
    )


def test_quantity_str_and_units():
    assert str(Quantity(Decimal("53"), "km")) == "53 'km'"
    assert str(Quantity(4, "days")) == "4 days"
    assert str(Quantity(1, "week")) == "1 week"
    assert Quantity(1, "weeks").unit == "week" and Quantity(1, "weeks").is_calendar
    assert not Quantity(1, "wk").is_calendar


def test_decimal_helpers():
    assert decimal_places(Decimal("1.5870")) == 4
    assert significant_places(Decimal("1.5870")) == 3
    assert significant_places(Decimal("100")) == 0
    assert round_half_away(Decimal("-0.5"), 0) == Decimal("-1")
    assert round_half_away(Decimal("3.14159"), 3) == Decimal("3.142")
    assert format_decimal(Decimal("1E+2")) == "100"


# ------------------------------------------------------------------ UCUM


@pytest.mark.parametrize(
    "unit,dims",
    [
        ("mg", (("g", 1),)),
        ("kg/m2", (("g", 1), ("m", -2))),
        ("10*3/uL", (("m", -3),)),
        ("mm[Hg]", (("g", 1), ("m", -1), ("s", -2))),
        ("[in_i]", (("m", 1),)),
        ("/min", (("s", -1),)),
        ("mg{total}", (("g", 1),)),
        ("{rbc}", ()),
        ("%", ()),
    ],
)
def test_ucum_parse(unit, dims):
    assert ucum.parse(unit).dims == dims


@pytest.mark.parametrize("unit", ["[s]", "foo", "m//s", "kg m"])
def test_ucum_invalid(unit):
    assert not ucum.is_valid(unit)


@pytest.mark.parametrize(
    "value,source,target,expected",
    [
        ("4.0", "g", "mg", "4000"),
        ("185", "[lb_av]", "kg", "83.91458845"),
        ("23", "Cel", "[degF]", "73.4"),
        ("1", "a", "d", "365.25"),
        ("52", "cm", "m", "0.52"),
        ("4", "cm.m", "m2", "0.04"),
        ("1", "[in_i]", "cm", "2.54"),
    ],
)
def test_ucum_convert(value, source, target, expected):
    assert ucum.convert(Decimal(value), source, target) == Decimal(expected)


def test_ucum_incommensurable():
    assert ucum.convert(Decimal(1), "cm", "s") is None
    assert not ucum.commensurable("cm2", "cm")
    assert ucum.commensurable("[in_i]", "cm")


def test_ucum_unit_algebra():
    assert ucum.multiply_units("cm", "m") == "cm.m"
    assert ucum.multiply_units("m/s", "s") == "m"
    assert ucum.multiply_units("1", "s", -1) == "/s"
    assert ucum.multiply_units("m", "s", -1) == "m/s"
    assert ucum.multiply_units("m", "m", -1) == "1"
