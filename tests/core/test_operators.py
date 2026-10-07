# _*_ coding: utf-8 _*_
"""Operator semantics (spec examples): equality, equivalence, comparison, logic, math."""

from decimal import Decimal

import pytest

from fhirpath.core import (
    EvaluationError,
    FPDate,
    FPDateTime,
    FPTime,
    Long,
    Quantity,
    evaluate,
)

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

T, F, E = [True], [False], []


def ev(expression, resource=None):
    return evaluate(resource, expression)


@pytest.mark.parametrize(
    "expression,expected",
    [
        # empty propagation
        ("{} = {}", E),
        ("{} != 'dummy'", E),
        ("1 = {}", E),
        # primitives
        ("'a' = 'A'", F),
        ("1 = 1.0", T),
        ("1.10 = 1.1", T),
        ("0.0 = 0", T),
        ("1.2 / 1.8 = 0.67", F),
        ("1 = 1L", T),
        ("true = 1", F),
        ("'1' = 1", F),
        # collections: ordered, pairwise
        ("(1|2|3) = (1|2|3)", T),
        ("(1|2|3) = (3|2|1)", F),
        ("(1|2) = (1|2|3)", F),
        # dates
        ("@2012 = @2012", T),
        ("@2012-01 = @2012", E),
        ("@2012-01-01T10:30:31 = @2012-01-01T10:30", E),
        ("@2012-01-01T10:30:31.0 = @2012-01-01T10:30:31", T),
        ("@2017-11-05T01:30:00.0-04:00 = @2017-11-05T00:30:00.0-05:00", T),
        ("@2012-04-15T15:00:00Z = @2012-04-15T10:00:00", E),
        ("@2012-04-15 = @2012-04-15T10:00:00", E),
        ("@2012-04-15 = @2012-04-16T10:00:00", F),
        ("@T10:30 = @T10:30:00", E),
        # quantities
        ("1 'h' = 3600 's'", T),
        ("1 hour = 3600 's'", T),
        ("1 year = 1 'a'", E),
        ("1 year = 12 months", T),
        ("1 year = 12 'mo'", E),
        ("1 week = 1 'wk'", T),
        ("7 days = 1 'wk'", T),
        ("1 'cm' = 10.0 'mm'", T),
        ("1 'cm' = 1 's'", E),
        ("23 'Cel' = 73.4 '[degF]'", T),
        ("23 = 23 '1'", T),
        ("4.0000 'g' = 4000.0 'mg'", T),
        ("1 != 2", T),
        ("{} != {}", E),
    ],
)
def test_equality(expression, expected):
    assert ev(expression) == expected


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("{} ~ {}", T),
        ("1 ~ {}", F),
        ("'abc' ~ 'ABC'", T),
        ("'a b' ~ 'a\tb'", T),
        ("'a     b' ~ 'a b'", F),
        ("1.2 / 1.8 ~ 0.67", T),
        ("0.0 ~ 0", T),
        ("@2012-01 ~ @2012", F),
        ("@2012-01-01T10:30:31.0 ~ @2012-01-01T10:30:31", T),
        ("@2012-01-01T10:30:31.1 ~ @2012-01-01T10:30:31", F),
        ("2.1 'cm' ~ 21 'mm'", T),
        ("4 'g' ~ 4040 'mg'", T),
        ("1 '[in_i]' ~ 2.5 'cm'", T),
        ("1 year ~ 1 'a'", T),
        ("1 year ~ 12 'mo'", T),
        ("1 year ~ 11 months", T),
        ("(1|2|3) ~ (3|2|1)", T),
        ("(1|2) ~ (1|2|3)", F),
        ("1 !~ 2", T),
    ],
)
def test_equivalence(expression, expected):
    assert ev(expression) == expected


def test_complex_equivalence():
    patient = {
        "resourceType": "Patient",
        "maritalStatus": {
            "coding": [{"system": "s", "code": "M", "display": "Married"}]
        },
        "contact": [
            {
                "relationship": [
                    {
                        "coding": [
                            {"system": "s", "code": "M", "display": "Other display"}
                        ]
                    }
                ]
            }
        ],
        "name": [{"id": "a", "family": "X"}, {"id": "b", "family": "X"}],
    }
    assert ev("maritalStatus ~ contact.relationship", patient) == T
    assert ev("maritalStatus = contact.relationship", patient) == F
    assert ev("maritalStatus.coding ~ contact.relationship.coding", patient) == T
    assert ev("name[0] ~ name[1]", patient) == T
    assert ev("name[0] = name[1]", patient) == F
    assert ev("name[0] = name[0]", patient) == T


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("1 < 2", T),
        ("1 < 1.5", T),
        ("'abc' > 'ABC'", T),
        ("{} < 1", E),
        ("@2018-03 > @2018-03-01", E),
        ("@2018-02 < @2018-03-01", T),
        ("@2018-03-01T10:30:00 > @2018-03-01T10:30:00.0", F),
        ("@2018-03-01T10:30:00 <= @2018-03-01T10:30:00.0", T),
        ("@2018-01-01T16:00:00+12:00 < @2018-01-01T15:00:00.0+10:00", T),
        ("@T10 < @T10:30", E),
        ("4 'm' > 4 'cm'", T),
        ("1 year > 1 'a'", E),
        ("6 months > 1 year", F),
        ("6 days < 1 week", T),
        ("1 'cm' < 1 's'", E),
        ("5L >= 5", T),
    ],
)
def test_comparison(expression, expected):
    assert ev(expression) == expected


@pytest.mark.parametrize(
    "expression",
    ["1 < 'a'", "true > false", "@2012 < @T10", "(1|2) < 3", "1 > 2 is Boolean"],
)
def test_comparison_errors(expression):
    with pytest.raises(EvaluationError):
        ev(expression)


@pytest.mark.parametrize("left", ["true", "false", "{}"])
@pytest.mark.parametrize("right", ["true", "false", "{}"])
@pytest.mark.parametrize("op", ["and", "or", "xor", "implies"])
def test_three_valued_logic(left, right, op):
    value = {"true": True, "false": False, "{}": None}
    a, b = value[left], value[right]
    tables = {
        "and": (False if False in (a, b) else (None if None in (a, b) else True)),
        "or": (True if True in (a, b) else (None if None in (a, b) else False)),
        "xor": (None if None in (a, b) else a != b),
        "implies": (
            True if a is False else (b if a is True else (True if b is True else None))
        ),
    }
    expected = tables[op]
    assert ev("%s %s %s" % (left, op, right)) == (
        [] if expected is None else [expected]
    )


def test_logic_singleton_rules():
    assert ev("(1 | 2).exists() and 1") == T  # non-boolean single item -> true
    with pytest.raises(EvaluationError):
        ev("(1 | 2) and true")
    assert ev("true.not()") == F and ev("{}.not()") == E


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("2 * 3", [6]),
        ("4 / 2", [Decimal("2.0")]),
        ("1 / 3 * 3 ~ 1", T),
        ("12 / 0", E),
        ("5 div 2", [2]),
        ("-5 div 2", [-2]),
        ("5.5 div 0.7", [Decimal(7)]),
        ("5 div 0", E),
        ("5 mod 2", [1]),
        ("-5 mod 2", [-1]),
        ("5.5 mod 0.7", [Decimal("0.6")]),
        ("5 mod 0", E),
        ("1 + 5L", [Long(6)]),
        ("5L + 4.5", [Decimal("9.5")]),
        ("'a' + 'b'", ["ab"]),
        ("'a' + {}", E),
        ("'ABC' & {} & 'DEF'", ["ABCDEF"]),
        ("2147483647 + 1", E),
        ("-(-5)", [5]),
        ("+5", [5]),
        ("-5.5 'mg'", [Quantity(Decimal("-5.5"), "mg")]),
        ("3 'm' + 3 'cm'", [Quantity(Decimal(303), "cm")]),
        ("2 + 2 'cm'", E),
        ("2 + 2 '1'", [Quantity(4, "1")]),
        ("1 'wk' + 2 days", [Quantity(9, "day")]),
        ("60 's' + 2 minutes", [Quantity(180, "second")]),
        ("1 year + 12 months", E),
        # spec examples disagree (0.5 minute vs most granular); both are equal
        ("1 minute - 30 's' = 0.5 minute", T),
        ("12 'cm' * 3 'cm'", [Quantity(36, "cm2")]),
        ("10 'm/s' * 10 's'", [Quantity(100, "m")]),
        ("3 * 2 'cm'", [Quantity(6, "cm")]),
        ("120 'm' / 60 's'", [Quantity(2, "m/s")]),
        ("60 / 1 's'", [Quantity(60, "/s")]),
        ("1 year * 2", E),
    ],
)
def test_math(expression, expected):
    assert ev(expression) == expected


@pytest.mark.parametrize(
    "expression", ["1 + 'a'", "true + 1", "-'a'", "(1|2) + 1", "1 & 2"]
)
def test_math_errors(expression):
    with pytest.raises(EvaluationError):
        ev(expression)


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("@1973-12-25 + 7 days", "1974-01-01"),
        ("@1973-12-25 + 7.9 days", "1974-01-01"),
        ("@2026-01-31 + 1 month", "2026-02-28"),
        ("@2019-03-01 + 24 months", "2021-03-01"),
        ("@2014 + 23 months", "2015"),
        ("@2016 + 365 days", "2017"),
        ("@2026-02 + 5 weeks", "2026-03"),
        ("@2026-02 - 1 day", "2026-02"),
        ("@2016-02-29 + 1 year", "2017-02-28"),
        (
            "@1973-12-25T00:00:00.000+10:00 + 42.53 seconds",
            "1973-12-25T00:00:42.530+10:00",
        ),
        ("@1973-12-25T00:00:00.000+10:00 + 1 'h'", "1973-12-25T01:00:00.000+10:00"),
        ("@T23:30:00 + 1 hour", "00:30:00"),
        ("@T00:30:00 - 1 hour", "23:30:00"),
    ],
)
def test_date_arithmetic(expression, expected):
    (result,) = ev(expression)
    assert result.isoformat() == expected


@pytest.mark.parametrize(
    "expression",
    [
        "@2012 + 1 'a'",
        "@2012 + 1 'mo'",
        "@T10:00 + 1 day",
        "@2012 + 1 'mg'",
        "@2012 + 1",
    ],
)
def test_date_arithmetic_errors(expression):
    with pytest.raises(EvaluationError):
        ev(expression)


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("(1|1|2|3).count()", [3]),
        ("1 in (1|2)", T),
        ("{} in (1|2)", E),
        ("1 in {}", F),
        ("(1|2) contains 2", T),
        ("(1|2) contains {}", E),
        ("{} contains 1", F),
        ("1 'm' in (100 'cm' | 2 'm')", T),
    ],
)
def test_collection_operators(expression, expected):
    assert ev(expression) == expected


def test_membership_errors():
    with pytest.raises(EvaluationError):
        ev("(1|2) in (1|2)")


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("1 is Integer", T),
        ("1 is System.Integer", T),
        ("1 is Decimal", F),
        ("1.0 is Decimal", T),
        ("5L is Long", T),
        ("'a' is String", T),
        ("@2015 is Date", T),
        ("@2015T is DateTime", T),
        ("@T10 is Time", T),
        ("1 'mg' is Quantity", T),
        ("1 is System.Patient", F),
        ("{} is Integer", E),
        ("1 as Integer", [1]),
        ("1 as String", E),
    ],
)
def test_type_operators(expression, expected):
    assert ev(expression) == expected


def test_type_operator_errors():
    with pytest.raises(EvaluationError):
        ev("1 is NoSuchType")
    with pytest.raises(EvaluationError):
        ev("(1 | 2) is Integer")


def test_fhir_types():
    patient = {
        "resourceType": "Patient",
        "active": True,
        "gender": "male",
        "name": [{"use": "official"}],
    }
    assert ev("Patient.active is boolean", patient) == T
    assert ev("Patient.active is FHIR.boolean", patient) == T
    assert ev("Patient.active is System.Boolean", patient) == F
    assert ev("Patient.gender is string", patient) == T  # code specialises string
    assert ev("Patient.gender as string", patient) == E  # but as/ofType are exact
    assert ev("Patient.gender.ofType(code)", patient) == ["male"]
    assert ev("Patient is DomainResource", patient) == T
    assert ev("Patient.name.ofType(HumanName).use", patient) == ["official"]


def test_temporal_results_have_system_types():
    assert isinstance(ev("@2014")[0], FPDate)
    assert isinstance(ev("@2014T")[0], FPDateTime)
    assert isinstance(ev("@T10")[0], FPTime)
