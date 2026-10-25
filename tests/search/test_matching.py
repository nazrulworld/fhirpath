# _*_ coding: utf-8 _*_
"""Matching semantics of the FHIR search specification (R5 §3.2.1.5): value
ranges and prefixes, string / token / uri matching, terminology modifiers,
composites, computed and extension parameters. The ``es_data`` tests run
against Elasticsearch (Docker); the others compile queries offline."""
import json

import pytest
from pytest import raises

from fhirpath.search.dialects.elasticsearch import ElasticSearchDialect
from fhirpath.search.exceptions import ValidationError
from fhirpath.search.ranges import (
    approximate_number_range,
    date_bounds,
    date_range,
    number_bounds,
    number_range,
)
from fhirpath.search.search import Search, SearchContext
from fhirpath.search.terminology import InMemoryTerminology
from tests._utils import TestElasticsearchEngine


@pytest.fixture
def offline_engine():
    engine = TestElasticsearchEngine(None)
    engine.dialect = ElasticSearchDialect(None)
    return engine


def compiled(engine, resource_type, query_string):
    context = SearchContext(engine, resource_type)
    query = Search(context, query_string=query_string).build()
    body = engine.dialect.compile(
        query._query, engine.calculate_field_index_name, engine.get_mapping
    )
    return json.loads(json.dumps(body["query"], default=str))


def total(engine, resource_type, *params):
    return Search(SearchContext(engine, resource_type), params=params)().total


# ---------------------------------------------------------------- the ranges


@pytest.mark.parametrize(
    "value,low,high",
    [
        ("100", "99.5", "100.5"),
        ("100.00", "99.995", "100.005"),
        ("1e2", "50", "150"),
        ("1.00e2", "99.5", "100.5"),
        ("0.8", "0.75", "0.85"),
    ],
)
def test_number_precision_range(value, low, high):
    from decimal import Decimal

    assert number_range(value) == (Decimal(low), Decimal(high))


def test_number_bounds_on_integers():
    # [99.5, 100.5) on an integer element is exactly 100
    assert number_bounds("100", "eq", "integer") == ("100", "101", False)
    # non-zero decimals can't match an integer
    assert number_bounds("100.5", "eq", "integer") == ("101", "101", False)


def test_number_approximation_is_ten_percent():
    from decimal import Decimal

    assert approximate_number_range("100") == (Decimal("90.0"), Decimal("110.0"))


@pytest.mark.parametrize(
    "value,element_type,low,high",
    [
        ("2013", "dateTime", "2013-01-01", "2014-01-01"),
        ("2013-02", "dateTime", "2013-02-01", "2013-03-01"),
        ("2013-01-14", "date", "2013-01-14", "2013-01-15"),
        ("2013-01-14T10:00", "dateTime", "2013-01-14T10:00:00", "2013-01-14T10:01:00"),
        (
            "2013-01-14T10:00:00Z",
            "instant",
            "2013-01-14T10:00:00+00:00",
            "2013-01-14T10:00:01+00:00",
        ),
        # a time range ending inside a day ends with that day for dates
        ("2013-01-14T10:00", "date", "2013-01-14", "2013-01-15"),
    ],
)
def test_date_precision_range(value, element_type, low, high):
    assert date_bounds(value, "eq", element_type) == (low, high, False)


def test_bad_date_is_rejected():
    for value in ("23 May 2009", "2013-1-1", "2013-01-14T10"):
        with raises(ValidationError):
            date_range(value)


def test_date_eq_is_one_range_query(offline_engine):
    query = compiled(offline_engine, "Patient", "birthdate=2013-01")
    assert query["bool"]["filter"][0] == {
        "range": {
            "patient_resource.birthDate": {"gte": "2013-01-01", "lt": "2013-02-01"}
        }
    }


def test_date_ne_never_matches_a_missing_value(offline_engine):
    query = compiled(offline_engine, "Patient", "birthdate=ne2013-01")
    alternatives = query["bool"]["filter"][0]["bool"]["should"]
    assert {"range": {"patient_resource.birthDate": {"lt": "2013-01-01"}}} in (
        alternatives
    )
    assert {"range": {"patient_resource.birthDate": {"gte": "2013-02-01"}}} in (
        alternatives
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1995", 1),
        ("1995-12", 1),
        ("1995-11", 0),
        ("1995-12-25", 1),
        ("ne1995-12", 0),
        ("ne1996", 1),
        # gt/lt/ge/le/sa/eb against the range of the value
        ("gt1995-11", 1),
        ("gt1995-12", 0),
        ("lt1995-12-26", 1),
        ("lt1995-12", 0),
        ("le1995-12", 1),
        ("ge1995-12", 1),
        ("sa1995-11-30", 1),
        ("sa1995-12-25", 0),
        ("eb1996", 1),
        ("eb1995-12-25", 0),
    ],
)
def test_search_date_ranges(es_data, engine, value, expected):
    assert total(engine, "Patient", ("birthdate", value)) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("7.2", 1),
        ("7.20", 1),
        ("7.25", 0),
        # 7 stands for [6.5, 7.5)
        ("7", 1),
        ("ne7.2", 0),
        ("ap7", 1),
        ("ap9", 0),
        # gt lt ge le compare exactly
        ("gt7.1", 1),
        ("gt7.2", 0),
        ("ge7.2", 1),
        ("lt7.2", 0),
        ("7.2|http://unitsofmeasure.org|g/dL", 1),
        ("7.2|http://unitsofmeasure.org|mg", 0),
    ],
)
def test_search_quantity_ranges(es_data, engine, value, expected):
    assert total(engine, "Observation", ("value-quantity", value)) == expected


def test_search_number_range(es_data, engine):
    assert total(engine, "ChargeItem", ("factor-override", "0.8")) == 1
    assert total(engine, "ChargeItem", ("factor-override", "0.80")) == 1
    assert total(engine, "ChargeItem", ("factor-override", "0.9")) == 0
    assert total(engine, "ChargeItem", ("factor-override", "ap0.85")) == 1


# ----------------------------------------------------------- string, token


def test_string_default_is_case_insensitive_prefix(offline_engine):
    query = compiled(offline_engine, "Patient", "family=sai")
    leaf = query["bool"]["filter"][0]["nested"]["query"]
    assert leaf == {
        "prefix": {
            "patient_resource.name.family": {"value": "sai", "case_insensitive": True}
        }
    }


def test_search_humanname(es_data, engine):
    assert total(engine, "Patient", ("name", "saint")) == 1
    assert total(engine, "Patient", ("name", "jon")) == 1
    assert total(engine, "Patient", ("name:exact", "Saint")) == 1
    assert total(engine, "Patient", ("name:exact", "saint")) == 0
    assert total(engine, "Patient", ("name:contains", "ONSO")) == 1


def test_token_without_system(es_data, engine):
    # |code: the code without a system
    assert total(engine, "Observation", ("code", "|718-7")) == 0
    assert total(engine, "Observation", ("code", "718-7")) == 1
    assert total(engine, "Observation", ("code", "http://loinc.org|718-7")) == 1
    assert total(engine, "Observation", ("code", "http://loinc.org|")) == 1
    # token matching is case-sensitive
    assert total(engine, "Observation", ("status", "FINAL")) == 0
    assert total(engine, "Observation", ("status", "final")) == 1


def test_contact_point_token_matches_the_value(es_data, engine):
    assert total(engine, "Patient", ("telecom", "2562000002")) == 1
    # system and use are not the ContactPoint's token
    assert total(engine, "Patient", ("telecom", "phone")) == 0


def test_token_text_modifiers(es_data, engine):
    assert total(engine, "Observation", ("code:text", "hemoglobin")) == 1
    assert total(engine, "Observation", ("code:text", "blood")) == 0


def test_uri_hierarchy(es_data, engine):
    base = "http://hl7.org/fhir/StructureDefinition"
    assert total(engine, "Patient", ("_profile", base)) == 0
    assert total(engine, "Patient", ("_profile:below", base)) == 1
    assert total(engine, "Patient", ("_profile:below", base + "/")) == 1
    assert total(engine, "Patient", ("_profile:below", "http://hl7.org/fh")) == 0
    assert total(engine, "Patient", ("_profile:above", base + "/Patient/x/y")) == 1
    assert total(engine, "Patient", ("_profile:above", base + "/Other")) == 0


def test_missing_ignores_extension_only_elements(offline_engine):
    query = compiled(offline_engine, "Patient", "address:missing=true")
    must_not = query["bool"]["filter"][0]["bool"]["must_not"]
    fields = json.dumps(must_not)
    # the elements of the address are tested, not the address object (which
    # may only carry extensions)
    assert "patient_resource.address.city" in fields
    assert "extension" not in fields


def test_search_missing(es_data, engine):
    assert total(engine, "Patient", ("address:missing", "false")) == 1
    assert total(engine, "Patient", ("address:missing", "true")) == 0
    assert total(engine, "Patient", ("deceased:missing", "true")) == 1


def test_computed_deceased(es_data, engine):
    # Patient.deceased.exists() and Patient.deceased != false
    assert total(engine, "Patient", ("deceased", "false")) == 1
    assert total(engine, "Patient", ("deceased", "true")) == 0
    assert total(engine, "Patient", ("deceased:not", "true")) == 1


def test_computed_deceased_query(offline_engine):
    query = compiled(offline_engine, "Patient", "deceased=true")
    should = query["bool"]["filter"][0]["bool"]["should"]
    text = json.dumps(should)
    assert "deceasedBoolean" in text and "deceasedDateTime" in text


# ----------------------------------------------------------- terminology


@pytest.fixture
def terminology(engine):
    service = InMemoryTerminology(
        fhir_release=engine.fhir_release,
        resources=[
            {
                "resourceType": "CodeSystem",
                "url": "http://loinc.org",
                "concept": [
                    {
                        "code": "LP-blood",
                        "concept": [{"code": "LP-hemo", "concept": [{"code": "718-7"}]}],
                    },
                    {"code": "LP-other"},
                ],
            },
            {
                "resourceType": "ValueSet",
                "id": "vs1",
                "url": "http://example.org/vs/hemo",
                "compose": {
                    "include": [
                        {
                            "system": "http://loinc.org",
                            "filter": [
                                {"property": "concept", "op": "is-a", "value": "LP-hemo"}
                            ],
                        }
                    ]
                },
            },
            {
                "resourceType": "ValueSet",
                "url": "http://example.org/vs/other",
                "compose": {
                    "include": [
                        {"system": "http://loinc.org", "concept": [{"code": "LP-other"}]}
                    ]
                },
            },
        ],
    )
    engine.terminology = service
    yield service
    del engine.terminology


def test_terminology_expansion(terminology):
    assert terminology.expand("http://example.org/vs/hemo") == [
        ("http://loinc.org", "LP-hemo"),
        ("http://loinc.org", "718-7"),
    ]
    assert terminology.expand("ValueSet/vs1") == terminology.expand(
        "http://example.org/vs/hemo"
    )
    assert terminology.expand("http://loinc.org?fhir_vs=isa/LP-hemo") == [
        ("http://loinc.org", "LP-hemo"),
        ("http://loinc.org", "718-7"),
    ]
    with raises(ValidationError, match="Unknown value set"):
        terminology.expand("http://example.org/vs/unknown")


def test_terminology_subsumption(terminology):
    assert [c for _, c in terminology.subsumption("http://loinc.org", "LP-blood", "below")] == [
        "LP-blood",
        "LP-hemo",
        "718-7",
    ]
    assert [c for _, c in terminology.subsumption(None, "718-7", "above")] == [
        "718-7",
        "LP-hemo",
        "LP-blood",
    ]
    with raises(ValidationError, match="hierarchy is unknown"):
        terminology.subsumption("http://snomed.info/sct", "123", "below")


def test_core_value_sets_are_known(offline_engine):
    from fhirpath.search.terminology import get_terminology

    codes = get_terminology(offline_engine).expand(
        "http://hl7.org/fhir/ValueSet/administrative-gender"
    )
    assert ("http://hl7.org/fhir/administrative-gender", "male") in codes


def test_search_in_and_not_in(es_data, engine, terminology):
    assert total(engine, "Observation", ("code:in", "http://example.org/vs/hemo")) == 1
    assert total(engine, "Observation", ("code:in", "ValueSet/vs1")) == 1
    assert total(engine, "Observation", ("code:in", "http://example.org/vs/other")) == 0
    assert total(engine, "Observation", ("code:not-in", "http://example.org/vs/hemo")) == 0
    assert (
        total(engine, "Observation", ("code:not-in", "http://example.org/vs/other"))
        == 1
    )
    # core value sets
    assert (
        total(
            engine,
            "Patient",
            ("gender:in", "http://hl7.org/fhir/ValueSet/administrative-gender"),
        )
        == 1
    )


def test_search_below_and_above(es_data, engine, terminology):
    assert total(engine, "Observation", ("code:below", "http://loinc.org|LP-blood")) == 1
    assert total(engine, "Observation", ("code:below", "http://loinc.org|LP-other")) == 0
    assert total(engine, "Observation", ("code:above", "http://loinc.org|718-7")) == 1
    assert total(engine, "Observation", ("code:above", "http://loinc.org|LP-hemo")) == 0


def test_of_type(offline_engine):
    query = compiled(
        offline_engine,
        "Patient",
        "identifier:of-type=http://terminology.hl7.org/CodeSystem/v2-0203|MR|446053",
    )
    text = json.dumps(query)
    assert "patient_resource.identifier.type.coding.code" in text
    assert '"446053"' in text
    with raises(ValidationError, match="of-type"):
        compiled(offline_engine, "Patient", "identifier:of-type=MR|446053")


def test_release_specific_modifiers(offline_engine):
    # code-text and text-advanced are R5 modifiers
    with raises(ValidationError, match="not supported in FHIR R4"):
        compiled(offline_engine, "Observation", "code:code-text=718")


# ------------------------------------------------------------- composites


def test_search_composite(es_data, engine):
    param = "code-value-quantity"
    assert total(engine, "Observation", (param, "http://loinc.org|718-7$7.2")) == 1
    assert total(engine, "Observation", (param, "http://loinc.org|718-7$8")) == 0
    # OR of tuples
    assert (
        total(
            engine,
            "Observation",
            (param, "http://loinc.org|1$1,http://loinc.org|718-7$ge7"),
        )
        == 1
    )
    # repeats are ANDed
    assert (
        total(
            engine,
            "Observation",
            (param, "http://loinc.org|718-7$7.2"),
            (param, "http://loinc.org|1$1"),
        )
        == 0
    )


def test_composite_components_match_in_the_same_element(offline_engine):
    query = compiled(
        offline_engine,
        "Observation",
        "component-code-value-quantity=http://loinc.org|8480-6$lt60",
    )
    nested = query["bool"]["filter"][0]["nested"]
    assert nested["path"] == "observation_resource.component"
    # both components inside the one nested component query
    assert len(nested["query"]["bool"]["filter"]) == 2


def test_combo_parameter(offline_engine):
    # combo-code: Observation.code | Observation.component.code
    query = compiled(offline_engine, "Observation", "combo-code=http://loinc.org|1")
    text = json.dumps(query)
    assert "observation_resource.code.coding" in text
    assert "observation_resource.component.code.coding" in text


# --------------------------------------------------- other element types


def test_range_element(offline_engine):
    # value.as(Range) of a composite component
    query = compiled(
        offline_engine, "ChargeItemDefinition", "context-type-quantity=HL7$5"
    )
    text = json.dumps(query)
    assert "useContext.valueRange.low.value" in text
    assert "useContext.valueRange.high.value" in text


def test_extension_value(offline_engine):
    search = Search(SearchContext(offline_engine, "Patient"))
    context = search.context
    path = context._dotted_path_to_path_context(
        "Patient.extension.where(url='http://example.org/race').valueCode"
    )
    path.search_param_type = "token"
    terms = []
    search.add_term((path, ("eq", "2106-3"), None), terms)
    (group,) = terms
    assert [t.path.path for t in group.terms] == [
        "Patient.extension.url",
        "Patient.extension.valueCode",
    ]
