# _*_ coding: utf-8 _*_
"""Function catalog (spec examples and edge cases)."""

from decimal import Decimal

import pytest

from fhirpath.core import EvaluationError, FPDateTime, Long, Quantity, evaluate
from fhirpath.core.context import Terminology

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

T, F, E = [True], [False], []

PATIENT = {
    "resourceType": "Patient",
    "id": "example",
    "active": True,
    "name": [
        {"use": "official", "family": "Chalmers", "given": ["Peter", "James"]},
        {"use": "usual", "given": ["Jim"]},
        {"use": "maiden", "family": "Windsor", "given": ["Peter", "James"]},
    ],
    "telecom": [{"use": "home"}, {"system": "phone", "value": "1", "use": "work"}],
}


def ev(expression, resource=None, **options):
    return evaluate(resource, expression, **options)


@pytest.mark.parametrize(
    "expression,expected",
    [
        # existence
        ("{}.empty()", T),
        ("(1|2).empty()", F),
        ("{}.exists()", F),
        ("(1|2|3).exists($this > 2)", T),
        ("{}.all($this > 0)", T),
        ("(1|2).all($this > 1)", F),
        ("(true|false).allTrue()", F),
        ("{}.allTrue()", T),
        ("(true|false).anyTrue()", T),
        ("{}.anyTrue()", F),
        ("(false).allFalse()", T),
        ("(true|false).anyFalse()", T),
        ("(1|2).subsetOf(1|2|3)", T),
        ("{}.subsetOf(1)", T),
        ("(1|2).subsetOf({})", F),
        ("(1|2|3).supersetOf(1|2)", T),
        ("(1|2).supersetOf({})", T),
        ("{}.supersetOf(1)", F),
        ("{}.count()", [0]),
        ("(1 | 2 | 2).count()", [2]),
        ("1.combine(1).distinct().count()", [1]),
        ("1 'm'.combine(100 'cm').isDistinct()", F),
        ("(1 'm' | 100 'cm').count()", [1]),
        # filtering & projection
        ("(1|2|3).where($this > 1)", [2, 3]),
        ("(1|2|3).where($index = 1)", [2]),
        ("(1|2|3).where({})", E),
        ("(1|2).select($this * 10)", [10, 20]),
        ("(1|2).select({})", E),
        ("(1|2).select(($this | 5))", [1, 5, 2, 5]),
        ("(1|2|3).ofType(Integer)", [1, 2, 3]),
        ("(1|'a'|2.0).ofType(String)", ["a"]),
        ("coalesce({}, 2, 3)", [2]),
        ("coalesce({}, {})", E),
        ("('3'|'1'|'10').sort()", ["1", "10", "3"]),
        ("(3|1|2).sort($this desc)", [3, 2, 1]),
        ("(3|1|2).sort(-$this)", [3, 2, 1]),
        # subsetting
        ("(1|2|3)[1]", [2]),
        ("(1|2|3)[5]", E),
        ("{}.single()", E),
        ("(1|2|3).first()", [1]),
        ("(1|2|3).last()", [3]),
        ("(1|2|3).tail()", [2, 3]),
        ("1.tail()", E),
        ("(1|2|3).skip(1)", [2, 3]),
        ("(1|2|3).skip(-1)", [1, 2, 3]),
        ("(1|2|3).take(2)", [1, 2]),
        ("(1|2|3).take(0)", E),
        ("(1|2|3).intersect(2|4)", [2]),
        ("(1|2|3).exclude(2)", [1, 3]),
        ("(1|2).combine(2).exclude(3)", [1, 2, 2]),
        # combining
        ("(1|1|2|3).union(2|3)", [1, 2, 3]),
        ("(1|2).combine(2|3)", [1, 2, 2, 3]),
        ("(1|2).combine(2|3, true)", [1, 2, 2, 3]),
    ],
)
def test_collection_functions(expression, expected):
    assert ev(expression) == expected


def test_single_errors_on_many():
    with pytest.raises(EvaluationError):
        ev("(1|2).single()")


def test_where_criteria_must_be_singleton():
    with pytest.raises(EvaluationError):
        ev("(1|2).where(($this | 5))")


def test_scoped_variables_restore():
    # the inner where() has its own $index, shadowing the outer one
    assert ev("(1|2).select((10|20).where($this > $index * 10).first())") == [10, 10]
    assert ev("(1|2|3).aggregate($this + $total, 0)") == [6]
    assert ev(
        "(1|2|3).aggregate(iif($total.empty(), $this, iif($this > $total, $this, $total)))"
    ) == [3]
    assert ev("telecom.select(iif(value = '1', $index, {}))", PATIENT) == [1]


def test_repeat():
    questionnaire = {
        "resourceType": "Questionnaire",
        "status": "active",
        "item": [
            {
                "linkId": "1",
                "type": "group",
                "item": [{"linkId": "1.1", "type": "string"}],
            },
            {"linkId": "2", "type": "string"},
        ],
    }
    assert ev("repeat(item).linkId", questionnaire) == ["1", "2", "1.1"]
    assert ev("repeatAll(item).linkId.count()", questionnaire) == [3]
    assert ev("descendants().ofType(code).count()", questionnaire) == [4]
    assert ev("(1|2).repeat(1)", None) == [1]


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("iif(true, 'a', 'b')", ["a"]),
        ("iif(false, 'a', 'b')", ["b"]),
        ("iif({}, 'a', 'b')", ["b"]),
        ("iif(false, 'a')", E),
        ("iif(1, 't', 'f')", ["t"]),
        ("iif(0, 't', 'f')", ["t"]),
        ("{}.iif(true, 'a', 'b')", ["a"]),
        ("{}.select(iif(true, 'a', 'b'))", E),
        ("iif(true, 'ok', (1|2).single())", ["ok"]),  # lazy branches
        ("'x'.iif($this = 'x', 'yes', 'no')", ["yes"]),
    ],
)
def test_iif(expression, expected):
    assert ev(expression) == expected


def test_iif_multi_item_input_errors():
    with pytest.raises(EvaluationError):
        ev("(1|2).iif(true, 'a', 'b')")


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("'yes'.toBoolean()", T),
        ("'T'.toBoolean()", T),
        ("'0.0'.toBoolean()", F),
        ("2.toBoolean()", E),
        ("'maybe'.convertsToBoolean()", F),
        ("'-12'.toInteger()", [-12]),
        ("'1.0'.toInteger()", E),
        ("true.toInteger()", [1]),
        ("'9999999999'.toLong()", [Long(9999999999)]),
        ("1.toLong()", [Long(1)]),
        ("'1.50'.toDecimal()", [Decimal("1.50")]),
        ("'1e3'.convertsToDecimal()", F),
        ("true.toDecimal()", [Decimal("1.0")]),
        ("'2014-01'.toDate() = @2014-01", T),
        ("@2024-01-15T23:30:00-05:00.toDate() = @2024-01-15", T),
        ("'150124'.toDate('ddMMyy') = @2024-01-15", T),
        ("'12-27'.toDate('MM-yy') = @2027-12", T),
        ("@2014-01-01.toDateTime() = @2014-01-01T", T),
        ("'2015-02-04T14:34:28Z'.toDateTime() = @2015-02-04T14:34:28Z", T),
        ("'14:34:28'.toTime() = @T14:34:28", T),
        ("'25:00'.convertsToTime()", F),
        ("1.toQuantity() = 1 '1'", T),
        ("'5.5 mg'.convertsToQuantity()", F),
        ("'5.5 \\'mg\\''.toQuantity() = 5.5 'mg'", T),
        ("'1 day'.toQuantity() = 1 'd'", T),
        ("52 'cm'.toQuantity('m') = 0.52 'm'", T),
        ("45.toQuantity('m')", E),
        ("1 'a'.toQuantity('d') = 365.25 'd'", T),
        ("7 days.toQuantity('wk') = 1 'wk'", T),
        ("182.5 days.toQuantity('a') = 0.5 'a'", T),
        ("1 'cm'.convertsToQuantity('s')", F),
        ("1.toString()", ["1"]),
        ("1.50.toString()", ["1.50"]),
        ("42L.toString()", ["42"]),
        ("true.toString()", ["true"]),
        (
            "@2014-01-25T14:30:00.000+10:00.toString()",
            ["2014-01-25T14:30:00.000+10:00"],
        ),
        ("@T10:30.toString()", ["10:30"]),
        ("53 'km'.toString()", ["53 'km'"]),
        ("4 days.toString()", ["4 days"]),
        ("{}.toString()", E),
    ],
)
def test_conversion(expression, expected):
    assert ev(expression) == expected


def test_conversion_errors_on_many():
    with pytest.raises(EvaluationError):
        ev("('1'|'2').toInteger()")


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("'abcdefg'.indexOf('bc')", [1]),
        ("'abc'.indexOf('')", [0]),
        ("'abc'.indexOf({})", E),
        ("'a🔥b'.indexOf('b')", [2]),
        ("'0123'.lastIndexOf('')", [4]),
        ("'abcabc'.lastIndexOf('bc')", [4]),
        ("'abcdefg'.substring(3)", ["defg"]),
        ("'abcdefg'.substring(1, 2)", ["bc"]),
        ("'abcdefg'.substring(6, 2)", ["g"]),
        ("'abcdefg'.substring(7)", E),
        ("'abcdefg'.substring(-1)", E),
        ("''.substring(0)", E),
        ("'abc'.substring(1, 0)", [""]),
        ("'abc'.startsWith('')", T),
        ("'abc'.endsWith('bc')", T),
        ("'abc'.contains('d')", F),
        ("'AbC'.upper()", ["ABC"]),
        ("'AbC'.lower()", ["abc"]),
        ("'abc'.replace('', 'x')", ["xaxbxcx"]),
        ("'abcb'.replace('b', 'B')", ["aBcB"]),
        ("'abc'.matches('^a')", T),
        ("'ABC'.matches('b', 'i')", T),
        ("'abc'.matches('')", E),
        ("'abc'.matchesFull('b')", F),
        ("'abc'.matchesFull('a.c')", T),
        ("'a\nb'.matches('a.b')", T),
        (
            "'11/30/1972'.replaceMatches('\\\\b(?<month>\\\\d{1,2})/(?<day>\\\\d{1,2})/(?<year>\\\\d{2,4})\\\\b', '${day}-${month}-${year}')",
            ["30-11-1972"],
        ),
        ("'abc123'.replaceMatches('[0-9]', '-')", ["abc---"]),
        ("'é'.length()", [1]),
        ("'🔥'.length()", [1]),
        ("'a🔥'.toChars()", ["a", "🔥"]),
        ("'  \tx \n'.trim()", ["x"]),
        ("'A,,C'.split(',')", ["A", "", "C"]),
        ("'ABC'.split(',')", ["ABC"]),
        ("('a'|'b'|'c').join(',')", ["a,b,c"]),
        ("('a'|'b').join()", ["ab"]),
        ("'test'.encode('base64')", ["dGVzdA=="]),
        ("'test'.encode('hex')", ["74657374"]),
        ("'dGVzdA=='.decode('base64')", ["test"]),
        ("'zz'.decode('hex')", E),
        ("'ä'.encode('ascii')", ["?"]),
        ("'a<b&\"'.escape('html')", ["a&lt;b&amp;&quot;"]),
        ("'a&lt;b'.unescape('html')", ["a<b"]),
        ("'a\"b'.escape('json')", ['a\\"b']),
        ("'a\\\\\"b'.unescape('json')", ['a"b']),
        ("{}.upper()", E),
    ],
)
def test_strings(expression, expected):
    assert ev(expression) == expected


@pytest.mark.parametrize(
    "expression",
    ["1.length()", "('a'|'b').length()", "'abc'.matches('a', 'x')", "(1|'a').join()"],
)
def test_string_errors(expression):
    with pytest.raises(EvaluationError):
        ev(expression)


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("(-5).abs()", [5]),
        ("(-5.5 'mg').abs() = 5.5 'mg'", T),
        ("(-1.1).ceiling()", [-1]),
        ("1.1.ceiling()", [2]),
        ("(-2.1).floor()", [-3]),
        ("(-1.56).truncate()", [-1]),
        ("1.5 'cm'.floor() = 1 'cm'", T),
        ("0.exp()", [Decimal(1)]),
        ("1.ln() = 0", T),
        ("0.ln()", E),
        ("16.log(2) ~ 4.0", T),
        ("2.power(3)", [8]),
        ("2.5.power(2) = 6.25", T),
        ("(-1).power(0.5)", E),
        ("3.14159.round(3)", [Decimal("3.142")]),
        ("(-0.5).round()", [Decimal(-1)]),
        ("2.5.round()", [Decimal(3)]),
        ("81.sqrt() = 9", T),
        ("(-1).sqrt()", E),
        ("{}.abs()", E),
    ],
)
def test_math(expression, expected):
    assert ev(expression) == expected


@pytest.mark.parametrize(
    "expression", ["0.log(10)", "1.round(-1)", "'a'.abs()", "(1|2).floor()"]
)
def test_math_errors(expression):
    with pytest.raises(EvaluationError):
        ev(expression)


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("(1|2|3).sum()", [6]),
        ("(1.5|2).sum()", [Decimal("3.5")]),
        ("(1 'mg'|2 'mg').sum() = 3 'mg'", T),
        ("{}.sum()", E),
        ("(3|1|2).min()", [1]),
        ("('b'|'a').max()", ["b"]),
        ("(@2014|@2015).max() = @2015", T),
        ("(5.5 | 4.7 | 4.8).avg()", [Decimal("5.0")]),
        ("(1|2).avg()", [Decimal("1.5")]),
    ],
)
def test_aggregates(expression, expected):
    assert ev(expression) == expected


def test_aggregate_type_errors():
    with pytest.raises(EvaluationError):
        ev("(1|'a').sum()")
    with pytest.raises(EvaluationError):
        ev("(1|@2014).min()")


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("@2014-01-05T10:30:00.000.yearOf()", [2014]),
        ("@2014.monthOf()", E),
        ("@2014-01-05.dayOf()", [5]),
        ("@2014-01-05.hourOf()", E),
        ("@T10:30:15.250.millisecondOf()", [250]),
        ("@2014-01-05T10:30:00-07:00.timezoneOffsetOf()", [Decimal(-7)]),
        ("@2014-01-05T10:30:00+08:45.timezoneOffsetOf()", [Decimal("8.75")]),
        ("@2014-01-05T10:30:00.dateOf() = @2014-01-05", T),
        ("@2014-01-05T10:30:00.timeOf() = @T10:30:00", T),
        ("1.58700.precision()", [5]),
        ("100.precision()", [0]),
        ("@2014.precision()", [4]),
        ("@2014-01-05T10:30:00.000.precision()", [17]),
        ("@T10:30.precision()", [4]),
        ("@T10:30:00.000.precision()", [9]),
        ("1.587.lowBoundary()", [Decimal("1.58650000")]),
        ("1.587.highBoundary()", [Decimal("1.58750000")]),
        ("1.587.lowBoundary(2)", [Decimal("1.58")]),
        ("(-1.587).lowBoundary(2)", [Decimal("-1.59")]),
        ("@2014.lowBoundary(6) = @2014-01", T),
        ("@2014.highBoundary(6) = @2014-12", T),
        ("@2014-02.highBoundary(8) = @2014-02-28", T),
        ("@T10:30.lowBoundary(9) = @T10:30:00.000", T),
        ("@2014-01-01T08:05+08:00.lowBoundary(17) = @2014-01-01T08:05:00.000+08:00", T),
        ("@2025-01-02.duration(@2025-01-07, 'week')", [0]),
        ("@2025-01-02.difference(@2025-01-07, 'week')", [1]),
        ("@2024-12-01.duration(@2025-09-01, 'year')", [0]),
        ("@2024-12-01.difference(@2025-09-01, 'year')", [1]),
        ("@2025-01-07.duration(@2025-01-02, 'day')", [-5]),
        ("@2025.duration(@2026-01-01, 'day')", E),
        ("1 year.comparable(1 'a')", F),
        ("1 'Cel'.comparable(1 '[degF]')", T),
        ("1.comparable(2)", T),
        ("1 'cm'.comparable(1 's')", F),
    ],
)
def test_date_time_utility(expression, expected):
    assert ev(expression) == expected


def test_now_today_are_deterministic():
    now = FPDateTime.parse("2024-05-06T07:08:09.010+02:00")
    assert ev("now() = now()", now=now) == T
    assert ev("now()", now=now) == [now]
    assert ev("today() = @2024-05-06", now=now) == T
    assert ev("timeOfDay() = @T07:08:09.010", now=now) == T
    assert ev("now() > today()") == E  # different precision


def test_define_variable():
    assert ev("defineVariable('v1', 'value1').select(%v1)", PATIENT) == ["value1"]
    assert ev("name.defineVariable('n', first()).select(%n.given)", PATIENT) == [
        "Peter",
        "James",
        "Peter",
        "James",
        "Peter",
        "James",
    ]
    with pytest.raises(EvaluationError):
        ev("defineVariable('v1').defineVariable('v1').select(%v1)", PATIENT)
    with pytest.raises(EvaluationError):
        ev("defineVariable('a', 1).id | %a", PATIENT)
    with pytest.raises(EvaluationError):
        ev("defineVariable('context', 1)", PATIENT)


def test_trace():
    logged = []
    result = ev(
        "name.trace('names', given).count()",
        PATIENT,
        tracer=lambda name, values: logged.append((name, values)),
    )
    assert result == [3]
    assert logged == [("names", ["Peter", "James", "Jim", "Peter", "James"])]


def test_type_function():
    (info,) = ev("1.type()")
    assert (info.namespace, info.name, info.baseType) == (
        "System",
        "Integer",
        "System.Any",
    )
    assert ev("('John' | 'Mary').type().name") == ["String", "String"]
    assert ev("Patient.type().namespace", PATIENT) == ["FHIR"]
    assert ev("Patient.active.type().name", PATIENT) == ["boolean"]
    assert ev("Patient.name.first().type().name", PATIENT) == ["HumanName"]


def test_children_and_descendants():
    assert ev("name[1].children().count()", PATIENT) == [2]
    assert ev("name.descendants().count()", PATIENT) == [10]
    assert ev("Patient.children().where($this = 'example').exists()", PATIENT) == T


def test_fhir_functions():
    assert ev("active.hasValue()", PATIENT) == T
    assert ev("name.hasValue()", PATIENT) == F
    assert ev("active.getValue()", PATIENT) == T
    assert ev("name.getValue()", PATIENT) == E
    assert ev("name.given.first().pathname()", PATIENT) == ["Patient.name[0].given[0]"]
    assert (
        ev("conformsTo('http://hl7.org/fhir/StructureDefinition/Patient')", PATIENT)
        == T
    )
    assert (
        ev("conformsTo('http://hl7.org/fhir/StructureDefinition/Observation')", PATIENT)
        == F
    )
    assert ev("'<div>hi <b>x</b></div>'.htmlChecks()") == T
    assert ev("'<script>x</script>'.htmlChecks()") == F
    assert ev("checkModifiers('').count()", PATIENT) == [1]


def test_terminology_hook():
    class Codes(Terminology):
        def member_of(self, value, valueset):
            return getattr(value, "value", None) is not None or value == "male"

        def subsumes(self, system, code_a, code_b):
            return code_a == "parent"

    patient = dict(PATIENT, gender="male")
    assert (
        ev(
            "gender.memberOf('http://hl7.org/fhir/ValueSet/administrative-gender')",
            patient,
            terminology=Codes(),
        )
        == T
    )
    coding = "Coding { system: 's', code: 'parent' }.subsumes(Coding { system: 's', code: 'child' })"
    assert ev(coding, terminology=Codes()) == T
    with pytest.raises(EvaluationError):
        ev("gender.memberOf('http://x')", patient)


def test_instance_selector():
    assert ev("Coding { system: 'http://x', code: 'a' }.code") == ["a"]
    assert (
        ev(
            "Coding { system: 'http://x', code: 'a' } ~ Coding { system: 'http://x', code: 'a', display: 'A' }"
        )
        == T
    )
    assert ev("Period {:}.exists()") == T
    assert ev("Coding { code: {} }.code") == E
    (quantity,) = ev("Quantity { value: 5, unit: 'mg' }.value")
    assert quantity == 5


def test_unknown_function_and_arity():
    with pytest.raises(EvaluationError):
        ev("noSuchFunction()")
    with pytest.raises(EvaluationError):
        ev("'a'.substring()")
    with pytest.raises(EvaluationError):
        ev("(1|2).count(1)")


def test_quantity_type_values():
    (q,) = ev("5 'mg' + 5 'mg'")
    assert q == Quantity(10, "mg")
