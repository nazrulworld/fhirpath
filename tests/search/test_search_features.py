# _*_ coding: utf-8 _*_
"""Search features (FHIR R5 search §3.2.1.6-3.2.1.7, search_filter.html):
_filter, _query, _text / _content, _list / _in, compartments, system-level
search, near and POST _search."""

import json

import pytest
from pytest import raises

from fhirpath.enums import FHIR_VERSION
from fhirpath.search.dialects.elasticsearch import ElasticSearchDialect
from fhirpath.search.engine import (
    EngineResult,
    EngineResultBody,
    EngineResultHeader,
    EngineResultRow,
)
from fhirpath.search.engine.es import ElasticsearchEngine
from fhirpath.search.exceptions import ValidationError
from fhirpath.search.filter import (
    Comparison,
    FilterSyntaxError,
    Logical,
    Not,
    ParamPath,
    parse_filter,
)
from fhirpath.search.query import QueryResult
from fhirpath.search.search import (
    NAMED_QUERIES,
    Search,
    SearchContext,
    active_members,
    fhir_search,
    register_named_query,
)
from tests._utils import TestElasticsearchEngine

PATIENT_ID = "19c5245f-89a8-49f8-b244-666b32adb92e"


@pytest.fixture
def offline_engine():
    engine = TestElasticsearchEngine(None)
    engine.dialect = ElasticSearchDialect(None)
    return engine


def total(engine, resource_type, query_string, **kwargs):
    search = Search(
        SearchContext(engine, resource_type),
        query_string=query_string or None,
        **kwargs,
    )
    return search().total


def compiled(engine, resource_type, query_string):
    search = Search(SearchContext(engine, resource_type), query_string=query_string)
    query = search.build()
    body = engine.dialect.compile(
        query._query, engine.calculate_field_index_name, engine.get_mapping
    )
    return json.loads(json.dumps(body["query"], default=str))


# -------------------------------------------------------------- _filter parse


def test_filter_grammar():
    node = parse_filter('given eq "peter" and birthdate ge 2014-10-10')
    assert node == Logical(
        "and",
        Comparison(ParamPath("given"), "eq", "peter", True),
        Comparison(ParamPath("birthdate"), "ge", "2014-10-10", False),
    )
    # no precedence: left to right
    node = parse_filter("a eq 1 or b eq 2 and c eq 3")
    assert node.operator == "and" and node.left.operator == "or"
    node = parse_filter("not (a eq 1)")
    assert isinstance(node, Not)
    # strings hold spaces, brackets and parentheses
    node = parse_filter('name co "a (b) [c]"')
    assert node.value == "a (b) [c]"


def test_filter_paths():
    node = parse_filter('subject.name co "peter"')
    assert node.path == ParamPath("subject", None, ParamPath("name"))
    node = parse_filter("related[type eq has-component].target re Observation/4")
    assert node.path.name == "related"
    assert node.path.filter == Comparison(
        ParamPath("type"), "eq", "has-component", False
    )
    assert node.path.next == ParamPath("target")
    node = parse_filter("_has:Observation:patient:code eq http://loinc.org|1234-5")
    assert node.path == ParamPath("code", has="_has:Observation:patient")


@pytest.mark.parametrize(
    "text",
    [
        "name",
        "name co",
        "name xx 1",
        "(name eq 1",
        "name eq 1 xor b eq 2",
        "name eq 1)",
        "_has:Observation:code eq 1",
    ],
)
def test_filter_syntax_errors(text):
    with raises(FilterSyntaxError):
        parse_filter(text)


# -------------------------------------------------------------- _filter search


@pytest.mark.parametrize(
    "resource_type,expression,expected",
    [
        ("Patient", 'name co "aint"', 1),
        ("Patient", 'name co "AINT"', 1),
        # string eq: the whole value, case-insensitive
        ("Patient", 'given eq "elector"', 1),
        ("Patient", 'given eq "elec"', 0),
        ("Patient", 'family sw "sai"', 1),
        ("Patient", 'family ew "INT"', 1),
        ("Patient", 'family ew "sai"', 0),
        ("Patient", "gender eq male", 1),
        ("Patient", "gender ne male", 0),
        ("Patient", "gender eq female or gender eq male", 1),
        ("Patient", "not (gender eq male)", 0),
        ("Patient", 'name sw "sai" and birthdate ge 1990-01-01', 1),
        ("Patient", "birthdate lt 1990", 0),
        ("Patient", "birthdate eq 1995-12", 1),
        ("Patient", "birthdate po 1995", 1),
        ("Patient", "birthdate pr true", 1),
        ("Patient", "birthdate pr false", 0),
        ("Patient", "_has:Observation:patient:code eq http://loinc.org|718-7", 1),
        ("Patient", "_has:Observation:patient:code eq loinc|1", 0),
        ("Observation", "code eq loinc|718-7", 1),
        ("Observation", 'code eq loinc|718-7 and subject.name co "saint"', 1),
        ("Observation", 'subject.name co "nobody"', 0),
        ("Observation", 'subject[gender eq male].name co "saint"', 1),
        ("Observation", 'subject[gender eq female].name co "saint"', 0),
        ("Observation", f"subject.id eq {PATIENT_ID}", 1),
        ("Observation", "value-quantity gt 7", 1),
        ("Observation", "value-quantity ap 7.2|ucum|g/dL", 1),
        (
            "Observation",
            "code-value-quantity eq code$loinc|718-7,value-quantity$7.2",
            1,
        ),
        (
            "Observation",
            "code-value-quantity ne code$loinc|718-7,value-quantity$7.2",
            0,
        ),
    ],
)
def test_filter_search(es_data, engine, resource_type, expression, expected):
    assert (
        total(engine, resource_type, "", params=(("_filter", expression),)) == expected
    )


def test_filter_errors(offline_engine):
    with raises(ValidationError, match="does not apply"):
        search = Search(
            SearchContext(offline_engine, "Patient"),
            params=(("_filter", "gender co x"),),
        )
        next(search.execute())
    with raises(ValidationError, match="not a reference"):
        search = Search(
            SearchContext(offline_engine, "Patient"),
            params=(("_filter", "gender.name eq x"),),
        )
        list(search.execute())


# ------------------------------------------------------------------- _query


def test_named_query(es_data, engine):
    def males_named(search, params):
        # a query-specific parameter becomes regular search parameters
        return [("gender", "male"), ("name", params.getone("who"))]

    register_named_query("males-named", males_named)
    try:
        assert total(engine, "Patient", "_query=males-named&who=saint") == 1
        assert total(engine, "Patient", "_query=males-named&who=nobody") == 0
    finally:
        NAMED_QUERIES.pop("males-named")


def test_unknown_named_query_is_refused(offline_engine):
    # even with lenient handling
    with raises(ValidationError, match="Unknown named query"):
        Search(SearchContext(offline_engine, "Patient"), query_string="_query=x")
    register_named_query("q", lambda search, params: params)
    try:
        with raises(ValidationError, match="Only one"):
            Search(
                SearchContext(offline_engine, "Patient"),
                query_string="_query=q&_query=q",
            )
    finally:
        NAMED_QUERIES.pop("q")


# ----------------------------------------------------------- _text, _content


def test_text_and_content(es_data, engine):
    assert total(engine, "Patient", "_text=heuvel") == 1
    assert total(engine, "Patient", "_text=acme healthcare") == 1
    assert total(engine, "Patient", "_text=heuvel AND nobody") == 0
    assert total(engine, "Patient", "_text=(heuvel OR nobody)") == 1
    assert total(engine, "Patient", "_text=nobody") == 0
    assert total(engine, "Patient", "_content=male") == 1
    assert total(engine, "Patient", "_content=female") == 0


def test_text_query(offline_engine):
    query = compiled(offline_engine, "Patient", "_text=bone OR liver")
    assert query["bool"]["must"][0] == {
        "simple_query_string": {
            "query": "bone | liver",
            "fields": ["patient_resource.text.div"],
            "default_operator": "and",
            "lenient": True,
        }
    }


# ------------------------------------------------------------- _list, _in


def make_result(*resources):
    body = EngineResultBody()
    for resource in resources:
        row = EngineResultRow()
        row.append(resource)
        body.append(row)
    return EngineResult(EngineResultHeader(total=len(resources)), body)


CONTAINERS = [
    {
        "resourceType": "List",
        "id": "l1",
        "entry": [
            {"item": {"reference": "Patient/p1"}},
            {"item": {"reference": "Patient/p2"}, "deleted": True},
            {"item": {"reference": "Observation/o1"}},
        ],
    },
    {
        "resourceType": "Group",
        "id": "g1",
        "member": [
            {"entity": {"reference": "Patient/p3"}},
            {"entity": {"reference": "Patient/p4"}, "inactive": True},
        ],
    },
    {
        "resourceType": "CareTeam",
        "id": "c1",
        "participant": [
            {"member": {"reference": "Patient/p5"}},
            {"member": {"reference": "Patient/p6"}, "period": {"end": "2001-01-01"}},
        ],
    },
]


def test_active_members():
    assert [r["reference"] for r in active_members(CONTAINERS[0])] == [
        "Patient/p1",
        "Observation/o1",
    ]
    assert [r["reference"] for r in active_members(CONTAINERS[1])] == ["Patient/p3"]
    assert [r["reference"] for r in active_members(CONTAINERS[2])] == ["Patient/p5"]


def containers_fetchall(query_result):
    types = [name for name, _ in query_result._query.get_from()]
    found = [c for c in CONTAINERS if c["resourceType"] in types]
    return make_result(*found)


class R5Engine(ElasticsearchEngine):
    def __init__(self):
        super().__init__(
            FHIR_VERSION.R5, lambda x: None, lambda x: ElasticSearchDialect(None)
        )

    def calculate_field_index_name(self, resource_type):
        return f"{resource_type.lower()}_resource"

    def get_mapping(self, resource_type):
        return None


def test_list(offline_engine, monkeypatch):
    monkeypatch.setattr(QueryResult, "fetchall", containers_fetchall)
    search = Search(SearchContext(offline_engine, "Patient"), query_string="_list=l1")
    outcome = search.execute()
    query = next(outcome)  # the List
    query = outcome.send(containers_fetchall(query))  # the main query
    assert search.id_restrictions == [({"Patient": {"p1"}}, False)]

    with raises(ValidationError, match="Functional list"):
        search = Search(
            SearchContext(offline_engine, "Patient"),
            query_string="_list=$current-allergies",
        )
        list(search.execute())


def test_in_r5(monkeypatch):
    monkeypatch.setattr(QueryResult, "fetchall", containers_fetchall)
    engine = R5Engine()
    search = Search(SearchContext(engine, "Patient"), query_string="_in=Group/g1")
    outcome = search.execute()
    query = next(outcome)
    outcome.send(containers_fetchall(query))
    assert search.id_restrictions == [({"Patient": {"p3"}}, False)]

    # a plain id may be a CareTeam, Group or List
    search = Search(SearchContext(engine, "Patient"), query_string="_in:not=c1")
    outcome = search.execute()
    query = next(outcome)
    for _ in range(2):
        query = outcome.send(containers_fetchall(query))
    outcome.send(containers_fetchall(query))
    assert search.id_restrictions == [({"Patient": {"p5", "p3", "p1"}}, True)]

    with raises(ValidationError, match="CareTeam, Group or List"):
        search = Search(SearchContext(engine, "Patient"), query_string="_in=Patient/1")
        list(search.execute())


def test_in_is_r5_only(offline_engine):
    # R4: an unknown parameter, ignored
    search = Search(SearchContext(offline_engine, "Patient"), query_string="_in=g1")
    assert search.ignored_params == ["_in"]


# ------------------------------------------------------------- compartments


def test_compartment_search(es_data, engine):
    assert total(engine, "Observation", "", compartment=f"Patient/{PATIENT_ID}") == 1
    assert total(engine, "Observation", "", compartment="Patient/nobody") == 0
    assert (
        total(engine, "Observation", "code=718-7", compartment=("Patient", PATIENT_ID))
        == 1
    )
    # the owner is in its compartment
    assert total(engine, "Patient", "", compartment=f"Patient/{PATIENT_ID}") == 1
    with raises(ValidationError, match="not in the Patient compartment"):
        total(engine, "Organization", "", compartment=f"Patient/{PATIENT_ID}")


def test_compartment_search_on_all_types(es_data, engine):
    search = Search(SearchContext(engine, None), compartment=f"Patient/{PATIENT_ID}")
    assert "Observation" in search.context.resource_types
    bundle = search(as_json=True)
    found = sorted({e["resource"]["resourceType"] for e in bundle["entry"]})
    assert found == ["MedicationRequest", "Observation", "Patient"]


def test_compartment_uses_every_parameter(offline_engine):
    query = compiled_compartment(offline_engine, "Observation", "Patient/1")
    text = json.dumps(query)
    # subject or performer
    assert "observation_resource.subject.reference" in text
    assert "observation_resource.performer.reference" in text


def compiled_compartment(engine, resource_type, compartment):
    search = Search(SearchContext(engine, resource_type), compartment=compartment)
    query = search.build()
    return engine.dialect.compile(
        query._query, engine.calculate_field_index_name, engine.get_mapping
    )


def test_bad_compartment(offline_engine):
    for compartment in ("Patient", "Patient/", "Unknown/1"):
        with raises(ValidationError):
            Search(SearchContext(offline_engine, None), compartment=compartment)


# -------------------------------------------------------- system-level search


def test_system_level_search(es_data, engine):
    # only the common parameters: others are ignored
    search = Search(
        SearchContext(engine, None), query_string=f"_id={PATIENT_ID}&gender=male"
    )
    assert search.ignored_params == ["gender"]
    assert search().total == 1
    # with _type, the parameters of those types
    assert total(engine, None, f"_type=Patient,Observation&_id={PATIENT_ID}") == 1


def test_types_with_different_parameter_types(offline_engine):
    search = Search(
        SearchContext(offline_engine, None),
        query_string="_type=Observation,Task&performer=Practitioner/1",
    )
    with raises(ValidationError, match="different types"):
        search.build()


# ---------------------------------------------------------------------- near


def test_near(offline_engine):
    query = compiled(offline_engine, "Location", "near=42.25|-83.69|10|[mi_us]")
    text = json.dumps(query)
    assert "location_resource.position.latitude" in text
    with raises(ValidationError, match="unknown distance unit"):
        compiled(offline_engine, "Location", "near=42.25|-83.69|10|parsec")
    with raises(ValidationError, match="near"):
        compiled(offline_engine, "Location", "near=north")


# ---------------------------------------------------------------- POST _search


def test_post_search(es_data, engine):
    context = SearchContext(engine, "Patient")
    search = Search(
        context, query_string="_count=5", form_body="gender=male&name=saint"
    )
    assert dict(search.applied_params) == {
        "_count": "5",
        "gender": "male",
        "name": "saint",
    }
    bundle = search(as_json=True)
    assert bundle["total"] == 1
    # the self link is a GET url with every applied parameter
    self_link = [link for link in bundle["link"] if link["relation"] == "self"][0]
    assert "gender=male" in self_link["url"] and "_count=5" in self_link["url"]

    bundle = fhir_search(
        SearchContext(engine, "Patient"),
        form_body=b"gender=female",
        response_as_dict=True,
    )
    assert bundle["total"] == 0


# ---------------------------------------------------------- CapabilityStatement


@pytest.mark.parametrize("release", ["STU3", "R4", "R4B", "R5"])
def test_capability_statement(release):
    from fhirpath.search.capability import capability_statement
    from fhirpath.search.utils import lookup_fhir_class
    from tests.search.test_versions import spec_available
    from tests._utils import has_internet_connection

    if not spec_available(release) and not has_internet_connection():
        pytest.skip("FHIR definitions are downloaded on first use")

    class Engine(ElasticsearchEngine):
        def __init__(self):
            super().__init__(
                FHIR_VERSION[release],
                lambda x: None,
                lambda x: ElasticSearchDialect(None),
            )

    statement = capability_statement(Engine(), ["Patient", "Observation"])
    # a valid resource of the release
    lookup_fhir_class("CapabilityStatement", FHIR_VERSION[release]).model_validate(
        statement
    )
    (rest,) = statement["rest"]
    patient = [r for r in rest["resource"] if r["type"] == "Patient"][0]
    names = {p["name"] for p in patient["searchParam"]}
    assert {"name", "birthdate", "gender", "_id"} <= names
    assert "Patient:general-practitioner" in patient["searchInclude"]
    assert "Observation:subject" in patient["searchRevInclude"]
    assert all(
        p.get("definition") for p in patient["searchParam"] if p["name"] == "name"
    )
    assert {"_id", "_lastUpdated", "_filter"} <= {
        p["name"] for p in rest["searchParam"]
    }


def test_named_queries_in_capability_statement(offline_engine):
    from fhirpath.search.capability import search_capabilities
    from fhirpath.search.search import NAMED_QUERY_DEFINITIONS

    register_named_query(
        "current-high-risk",
        lambda search, params: params,
        "http://example.org/OperationDefinition/current-high-risk",
    )
    try:
        rest = search_capabilities(offline_engine, ["Patient"])
    finally:
        NAMED_QUERIES.pop("current-high-risk")
        NAMED_QUERY_DEFINITIONS.pop("current-high-risk")
    assert rest["operation"] == [
        {
            "name": "current-high-risk",
            "definition": "http://example.org/OperationDefinition/current-high-risk",
        }
    ]


@pytest.mark.asyncio
async def test_async_filter_and_compartment(es_data, async_engine):
    from fhirpath.search.search import AsyncSearch

    search = AsyncSearch(
        SearchContext(async_engine, "Observation"),
        params=(("_filter", 'code eq loinc|718-7 and subject.name co "saint"'),),
    )
    bundle = await search()
    assert bundle.total == 1

    search = AsyncSearch(
        SearchContext(async_engine, "Observation"),
        params=(("_include:iterate", "Observation:subject"),),
        compartment=f"Patient/{PATIENT_ID}",
    )
    bundle = await search(as_json=True)
    assert [e["search"]["mode"] for e in bundle["entry"]] == ["match", "include"]
