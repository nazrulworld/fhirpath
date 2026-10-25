# _*_ coding: utf-8 _*_
"""Result parameters (FHIR R5 search §3.2.1.7): _total, _count, _maxresults,
_score, _summary / _elements (SUBSETTED), _contained, _sort and _graph."""
import json

import pytest
from pytest import raises

from fhirpath.enums import SortOrderType
from fhirpath.search.dialects.elasticsearch import ElasticSearchDialect
from fhirpath.search.engine import (
    EngineResult,
    EngineResultBody,
    EngineResultHeader,
    EngineResultRow,
)
from fhirpath.search.exceptions import ValidationError
from fhirpath.search.graph import (
    GRAPH_DEFINITIONS,
    graph_links,
    register_graph_definition,
)
from fhirpath.search.query import QueryResult
from fhirpath.search.search import Search, SearchContext, subsetting_elements
from tests._utils import TestElasticsearchEngine, load_organizations_data


@pytest.fixture
def offline_engine():
    engine = TestElasticsearchEngine(None)
    engine.dialect = ElasticSearchDialect(None)
    return engine


def compile_body(engine, resource_type, query_string):
    search = Search(SearchContext(engine, resource_type), query_string=query_string)
    query = search.build()
    return engine.dialect.compile(
        query._query, engine.calculate_field_index_name, engine.get_mapping
    )


def links(bundle):
    return {link["relation"]: link["url"] for link in bundle["link"]}


def run(engine, resource_type, query_string, **kwargs):
    return Search(SearchContext(engine, resource_type), query_string=query_string)(
        as_json=True, **kwargs
    )


# --------------------------------------------------------- total and paging


def test_total_none_and_accurate(es_data, engine):
    bundle = run(engine, "Patient", "_total=none")
    assert "total" not in bundle
    assert len(bundle["entry"]) == 1

    bundle = run(engine, "Patient", "_total=accurate")
    assert bundle["total"] == 1


def test_total_accurate_tracks_all_hits(offline_engine):
    body = compile_body(offline_engine, "Patient", "_total=accurate")
    assert body["track_total_hits"] is True
    body = compile_body(offline_engine, "Patient", "_total=estimate")
    assert "track_total_hits" not in body


def test_bad_result_parameter_values(offline_engine):
    for query_string in (
        "_total=all",
        "_summary=yes",
        "_count=-1",
        "_count=ten",
        "_score=maybe",
        "_contained=some",
        "_containedType=other",
        "_sort=name:exact",
    ):
        with raises(ValidationError):
            compile_body(offline_engine, "Patient", query_string)


def test_count_zero_is_summary_count(es_data, engine):
    bundle = run(engine, "Patient", "_count=0")
    assert bundle["total"] == 1
    assert bundle.get("entry", []) == []
    assert set(links(bundle)) == {"self"}


def test_maxresults(es_data, engine):
    load_organizations_data(es_data[0], 5)  # 6 organizations
    bundle = run(engine, "Organization", "_count=2&_maxresults=3")
    assert bundle["total"] == 6
    assert len(bundle["entry"]) == 2
    # two pages only
    assert "page=2" in links(bundle)["last"]

    bundle = run(engine, "Organization", "_count=2&_maxresults=3&page=2")
    assert len(bundle["entry"]) == 1
    assert "next" not in links(bundle)
    # _maxresults is applied: it is in the self link
    assert "_maxresults=3" in links(bundle)["self"]


def test_score(es_data, engine):
    bundle = run(engine, "Patient", "_score=true")
    assert bundle["entry"][0]["search"]["score"] == 1.0
    bundle = run(engine, "Patient", "")
    assert "score" not in bundle["entry"][0]["search"]


# ----------------------------------------------------- _summary / _elements


def tags(resource):
    return [t["code"] for t in resource.get("meta", {}).get("tag", [])]


def test_summary_is_tagged_subsetted(es_data, engine):
    bundle = run(engine, "Patient", "_summary=true")
    assert "SUBSETTED" in tags(bundle["entry"][0]["resource"])
    bundle = run(engine, "Patient", "_summary=false")
    assert "SUBSETTED" not in tags(bundle["entry"][0]["resource"])


def test_summary_text_excludes_includes(offline_engine):
    with raises(ValidationError, match="_summary=text"):
        Search(
            SearchContext(offline_engine, "Observation"),
            query_string="_summary=text&_include=Observation:subject",
        )


def test_elements_take_choice_names(es_data, engine):
    bundle = run(engine, "Observation", "_elements=value")
    resource = bundle["entry"][0]["resource"]
    assert resource["valueQuantity"]["value"] == 7.2
    # status and code are mandatory
    assert resource["status"] == "final"
    assert "code" in resource
    assert "subject" not in resource
    assert "SUBSETTED" in tags(resource)


def test_elements_add_mandatory_and_modifier_elements():
    from fhirpath.enums import FHIR_VERSION

    known = subsetting_elements("Observation", FHIR_VERSION.R4)
    assert {"status", "code"} <= set(known["mandatory"])
    assert "status" in known["modifier"]
    assert {"valueQuantity", "valueCodeableConcept"} <= set(known["names"]["value"])


def test_type_prefixed_elements_apply_to_includes(es_data, engine):
    bundle = run(
        engine,
        "Observation",
        "_elements=Observation.status,Patient.gender&_include=Observation:subject",
    )
    observation, patient = [e["resource"] for e in bundle["entry"]]
    assert "valueQuantity" not in observation
    assert patient["gender"] == "male"
    assert "name" not in patient
    assert "SUBSETTED" in tags(patient)


# ----------------------------------------------------------------- contained


def test_contained_search_is_not_supported(offline_engine):
    search = Search(
        SearchContext(offline_engine, "Medication"),
        query_string="_contained=true&code=1",
    )
    assert "_contained" not in search.applied_params
    assert any("_contained" in i["diagnostics"] for i in search.outcome_issues())

    with raises(ValidationError, match="_contained=true is not supported"):
        Search(
            SearchContext(offline_engine, "Medication"),
            query_string="_contained=true",
            handling="strict",
        )
    # the default is applied
    search = Search(
        SearchContext(offline_engine, "Medication"), query_string="_contained=false"
    )
    assert search.applied_params["_contained"] == "false"


# ---------------------------------------------------------------------- _sort


def test_sort_on_complex_and_nested_elements(offline_engine):
    body = compile_body(offline_engine, "Patient", "_sort=-name,birthdate")
    assert body["sort"][0] == {
        "patient_resource.name.family": {
            "order": "desc",
            "unmapped_type": "long",
            "nested": {"path": "patient_resource.name"},
        }
    }
    assert "patient_resource.name.given" in body["sort"][1]
    assert "patient_resource.birthDate" in body["sort"][2]

    body = compile_body(offline_engine, "Observation", "_sort=code")
    assert "observation_resource.code.coding.code" in body["sort"][0]
    body = compile_body(offline_engine, "Observation", "_sort=code:text")
    assert "observation_resource.code.text" in body["sort"][0]
    # every path of the parameter (Organization.name | Organization.alias)
    body = compile_body(offline_engine, "Organization", "_sort=name")
    assert len(body["sort"]) == 2


def test_sort_search(es_data, engine):
    load_organizations_data(es_data[0], 1)
    bundle = run(engine, "Patient", "_sort=-name")
    assert bundle["total"] == 1


def make_result(*resources):
    body = EngineResultBody()
    for resource in resources:
        row = EngineResultRow()
        row.append(resource)
        body.append(row)
    return EngineResult(EngineResultHeader(total=len(resources)), body)


SORT_STORE = [
    {"resourceType": "Observation", "id": "o1", "subject": {"reference": "Patient/b"}},
    {"resourceType": "Observation", "id": "o2", "subject": {"reference": "Patient/a"}},
    {"resourceType": "Observation", "id": "o3"},
    {"resourceType": "Observation", "id": "o4", "subject": {"reference": "Patient/c"}},
    {"resourceType": "Patient", "id": "a", "name": [{"family": "anders"}]},
    {"resourceType": "Patient", "id": "b", "name": [{"family": "Berg"}]},
    {"resourceType": "Patient", "id": "c", "name": [{"family": "cole"}]},
]


def store_fetchall(query_result):
    types = [name for name, _ in query_result._query.get_from()]
    found = [r for r in SORT_STORE if r["resourceType"] in types]
    leaves = []

    def walk(terms):
        for term in terms:
            if hasattr(term, "terms"):
                walk(term.terms)
            else:
                leaves.append(term)

    walk(query_result._query.get_where())
    ids = [str(t.value.raw) for t in leaves if str(t.path).endswith(".id")]
    if ids:
        found = [r for r in found if r["id"] in ",".join(ids).split(",")]
    return make_result(*found)


def test_chained_sort(offline_engine, monkeypatch):
    monkeypatch.setattr(QueryResult, "fetchall", store_fetchall)
    search = Search(
        SearchContext(offline_engine, "Observation"),
        query_string="_sort=subject:Patient.name",
    )
    bundle = search(as_json=True)
    # case-insensitive, missing values last
    assert [e["resource"]["id"] for e in bundle["entry"]] == ["o2", "o1", "o4", "o3"]
    assert bundle["total"] == 4

    search = Search(
        SearchContext(offline_engine, "Observation"),
        query_string="_sort=-subject:Patient.name&_count=2&page=1",
    )
    bundle = search(as_json=True)
    assert [e["resource"]["id"] for e in bundle["entry"]] == ["o4", "o1"]


# --------------------------------------------------------------------- _graph


def test_graph_links_r4_and_r5():
    r4 = {
        "resourceType": "GraphDefinition",
        "start": "Composition",
        "link": [
            {
                "path": "Composition.subject",
                "target": [
                    {
                        "type": "Patient",
                        "link": [
                            {"path": "Patient.link.other", "target": [{"type": "Patient"}]}
                        ],
                    }
                ],
            }
        ],
    }
    (link,) = graph_links(r4)
    assert (link.path, link.target_type) == ("Composition.subject", "Patient")
    assert link.links[0].path == "Patient.link.other"

    r5 = {
        "resourceType": "GraphDefinition",
        "start": "comp",
        "node": [
            {"nodeId": "comp", "type": "Composition"},
            {"nodeId": "pat", "type": "Patient"},
        ],
        "link": [{"sourceId": "comp", "path": "Composition.subject", "targetId": "pat"}],
    }
    (link,) = graph_links(r5)
    assert (link.path, link.target_type) == ("Composition.subject", "Patient")


GRAPH_STORE = [
    {
        "resourceType": "Observation",
        "id": "o1",
        "subject": {"reference": "Patient/p1"},
    },
    {
        "resourceType": "Patient",
        "id": "p1",
        "managingOrganization": {"reference": "Organization/org1"},
    },
    {"resourceType": "Organization", "id": "org1"},
    {"resourceType": "Encounter", "id": "e1", "subject": {"reference": "Patient/p1"}},
]


def graph_fetchall(query_result):
    types = [name for name, _ in query_result._query.get_from()]
    leaves = []

    def walk(terms):
        for term in terms:
            if hasattr(term, "terms"):
                walk(term.terms)
            else:
                leaves.append(term)

    walk(query_result._query.get_where())
    values = [str(t.value.raw) for t in leaves if getattr(t, "value", None)]
    found = []
    for resource in GRAPH_STORE:
        if resource["resourceType"] not in types:
            continue
        if not values:
            found.append(resource)
        elif resource["id"] in ",".join(values).split(","):
            found.append(resource)
        elif resource.get("subject", {}).get("reference") in values:
            found.append(resource)
    return make_result(*found)


def test_graph_includes(offline_engine, monkeypatch):
    monkeypatch.setattr(QueryResult, "fetchall", graph_fetchall)
    register_graph_definition(
        {
            "resourceType": "GraphDefinition",
            "id": "obs-context",
            "url": "http://example.org/GraphDefinition/obs-context",
            "start": "Observation",
            "link": [
                {
                    "path": "Observation.subject",
                    "target": [
                        {
                            "type": "Patient",
                            "link": [
                                {
                                    "path": "Patient.managingOrganization",
                                    "target": [{"type": "Organization"}],
                                },
                                {
                                    "target": [
                                        {"type": "Encounter", "params": "subject={ref}"}
                                    ]
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    )
    try:
        search = Search(
            SearchContext(offline_engine, "Observation"),
            query_string="_graph=http://example.org/GraphDefinition/obs-context",
        )
        bundle = search(as_json=True)
    finally:
        GRAPH_DEFINITIONS.clear()
    assert [(e["resource"]["id"], e["search"]["mode"]) for e in bundle["entry"]] == [
        ("o1", "match"),
        ("p1", "include"),
        ("org1", "include"),
        ("e1", "include"),
    ]


def test_unknown_graph(offline_engine, monkeypatch):
    monkeypatch.setattr(QueryResult, "fetchall", lambda q: make_result())
    search = Search(
        SearchContext(offline_engine, "Observation"), query_string="_graph=unknown"
    )
    with raises(ValidationError, match="Unknown GraphDefinition"):
        search()
