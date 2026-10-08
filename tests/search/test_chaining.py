# _*_ coding: utf-8 _*_
"""Chained search parameters (FHIR R5 search §3.2.1.6.5) without a search backend:
sub-queries are answered with fake engine results."""

import re

import pytest
from pytest import raises

from fhirpath.search.engine import (
    EngineResult,
    EngineResultBody,
    EngineResultHeader,
    EngineResultRow,
)
from fhirpath.search.exceptions import ValidationError
from fhirpath.search.query import QueryResult
from fhirpath.search.search import (
    AsyncSearch,
    Search,
    SearchContext,
    run_chain_resolver,
    run_chain_resolver_async,
)
from tests._utils import TestElasticsearchEngine


@pytest.fixture
def offline_engine():
    return TestElasticsearchEngine(None)


def make_result(*resources):
    body = EngineResultBody()
    for resource in resources:
        row = EngineResultRow()
        row.append(resource)
        body.append(row)
    return EngineResult(EngineResultHeader(total=len(resources)), body)


def resource_types(query_result):
    return [name for name, _ in query_result._query.get_from()]


def drive(resolver, answers):
    """Feed ``answers`` (resource type -> resources) to the yielded sub-queries."""
    asked = []
    try:
        query = next(resolver)
        while True:
            (resource_type,) = resource_types(query)
            asked.append(resource_type)
            query = resolver.send(make_result(*answers.get(resource_type, [])))
    except StopIteration as stop:
        return stop.value, asked


def test_chain_params_are_separated(offline_engine):
    params = (
        ("subject:Patient.name", "peter"),
        ("subject.name", ""),
        ("status", "final"),
    )
    search = Search(SearchContext(offline_engine, "Observation"), params=params)
    # the empty chained value is ignored, like any empty parameter
    assert search.chain_params == [("subject:Patient.name", "peter")]
    assert list(search.search_params.keys()) == ["status"]


def test_parse_chain_link():
    assert Search.parse_chain_link("subject") == ("subject", None)
    assert Search.parse_chain_link("subject:Patient") == ("subject", "Patient")
    for bad in ("subject:", ":Patient", "subject:Patient:x"):
        with raises(ValidationError):
            Search.parse_chain_link(bad)


def test_typed_chain(offline_engine):
    search = Search(
        SearchContext(offline_engine, "DiagnosticReport"),
        params=(("subject:Patient.name", "peter"),),
    )
    references, asked = drive(
        search.chain(*search.chain_params[0]),
        {"Patient": [{"resourceType": "Patient", "id": "p1"}]},
    )
    assert asked == ["Patient"]
    assert references == ["Patient/p1"]
    assert search.chain_reference_name("subject:Patient.name") == "subject"


def test_untyped_chain_follows_every_target_defining_the_param(offline_engine):
    search = Search(
        SearchContext(offline_engine, "DiagnosticReport"),
        params=(("subject.name", "peter"),),
    )
    references, asked = drive(
        search.chain(*search.chain_params[0]),
        {
            "Patient": [{"resourceType": "Patient", "id": "p1"}],
            "Location": [{"resourceType": "Location", "id": "l1"}],
        },
    )
    # DiagnosticReport.subject -> Group | Device | Patient | Location; in R4 only
    # Patient and Location define "name" (Device has "device-name", Group none)
    assert asked == ["Patient", "Location"]
    assert references == ["Patient/p1", "Location/l1"]


def test_multi_level_chain(offline_engine):
    search = Search(
        SearchContext(offline_engine, "Encounter"),
        params=(("subject:Patient.organization.name", "Burgers"),),
    )
    references, asked = drive(
        search.chain(*search.chain_params[0]),
        {
            "Organization": [{"resourceType": "Organization", "id": "o1"}],
            "Patient": [{"resourceType": "Patient", "id": "p1"}],
        },
    )
    # innermost link first
    assert asked == ["Organization", "Patient"]
    assert references == ["Patient/p1"]


def test_multi_level_chain_without_inner_match(offline_engine):
    search = Search(
        SearchContext(offline_engine, "Encounter"),
        params=(("subject:Patient.organization.name", "nobody"),),
    )
    references, asked = drive(search.chain(*search.chain_params[0]), {})
    # no organization -> the Patient sub-query is never sent
    assert asked == ["Organization"]
    assert references == []


def test_chain_errors(offline_engine):
    def resolve(resource_type, name):
        search = Search(
            SearchContext(offline_engine, resource_type), params=((name, "x"),)
        )
        return drive(search.chain(name, "x"), {})

    with raises(
        ValidationError,
        match=re.escape(
            "chained search parameter Observation.code "
            "must be of type 'reference', got token"
        ),
    ):
        resolve("Observation", "code.name")

    with raises(
        ValidationError,
        match=re.escape(
            "the search param Observation.subject may refer to "
            "Group, Device, Patient, Location, not to Practitioner"
        ),
    ):
        resolve("Observation", "subject:Practitioner.name")

    with raises(
        ValidationError,
        match=re.escape(
            "No search definition is available for search parameter "
            "``unknown`` on any target of ``Observation.subject``."
        ),
    ):
        resolve("Observation", "subject.unknown")

    with raises(
        ValidationError,
        match=re.escape(
            "No search definition is available for search "
            "parameter ``unknown`` on Resource ``Observation``."
        ),
    ):
        resolve("Observation", "unknown.name")

    with raises(NotImplementedError):
        resolve("Encounter", "patient._has:Group:member:_id")


def test_build_with_chained_references(offline_engine):
    search = Search(
        SearchContext(offline_engine, "Observation"),
        params=(("subject:Patient.name", "peter"), ("status", "final")),
    )
    search.chained_references = [("subject", ["Patient/p1", "Patient/p2"])]
    query_result = search.build()
    compiled = offline_engine.dialect.compile(
        query_result._query,
        calculate_field_index_name=offline_engine.calculate_field_index_name,
        get_mapping=offline_engine.get_mapping,
    )
    should = [
        clause["bool"]["should"]
        for clause in compiled["query"]["bool"]["filter"]
        if "bool" in clause
    ]
    assert should == [
        [
            {"term": {"observation_resource.subject.reference": "Patient/p1"}},
            {"term": {"observation_resource.subject.reference": "Patient/p2"}},
        ]
    ]


def test_search_with_chain(offline_engine, monkeypatch):
    executed = []

    def fetchall(query_result):
        types = resource_types(query_result)
        executed.append(types)
        if types == ["Patient"]:
            return make_result({"resourceType": "Patient", "id": "p1"})
        return make_result(
            {
                "resourceType": "Observation",
                "id": "o1",
                "status": "final",
                "code": {"text": "test"},
            }
        )

    monkeypatch.setattr(QueryResult, "fetchall", fetchall)

    search = Search(
        SearchContext(offline_engine, "Observation"),
        params=(("subject:Patient.name", "peter"),),
    )
    bundle = search()
    assert executed == [["Patient"], ["Observation"]]
    assert search.chained_references == [("subject", ["Patient/p1"])]
    assert bundle.total == 1


def test_search_with_unsatisfied_chain_is_empty(offline_engine, monkeypatch):
    executed = []

    def fetchall(query_result):
        executed.append(resource_types(query_result))
        return make_result()

    monkeypatch.setattr(QueryResult, "fetchall", fetchall)

    search = Search(
        SearchContext(offline_engine, "Observation"),
        params=(("subject:Patient.name", "nobody"),),
    )
    bundle = search()
    # the main query is not run at all
    assert executed == [["Patient"]]
    assert bundle.total == 0


def test_run_chain_resolver():
    class FakeQuery:
        def __init__(self, result):
            self.result = result

        def fetchall(self):
            return self.result

    def resolver():
        first = yield FakeQuery(1)
        second = yield FakeQuery(2)
        return [first, second]

    assert run_chain_resolver(resolver()) == [1, 2]


@pytest.mark.asyncio
async def test_run_chain_resolver_async():
    class FakeQuery:
        def __init__(self, result):
            self.result = result

        async def fetchall(self):
            return self.result

    def resolver():
        first = yield FakeQuery(1)
        return [first]

    assert await run_chain_resolver_async(resolver()) == [1]


@pytest.mark.asyncio
async def test_async_search_with_unsatisfied_chain_is_empty(
    offline_engine, monkeypatch
):
    async def fetchall(query_result):
        return make_result()

    monkeypatch.setattr(QueryResult, "fetchall", fetchall)

    search = AsyncSearch(
        SearchContext(offline_engine, "Observation"),
        params=(("subject:Patient.name", "nobody"),),
    )
    bundle = await search()
    assert bundle.total == 0
