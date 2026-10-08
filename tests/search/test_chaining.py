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
    reference_targets,
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


GROUP_102 = {
    "resourceType": "Group",
    "id": "102",
    "type": "person",
    "actual": True,
    "member": [
        {"entity": {"reference": "Patient/p1"}},
        {"entity": {"reference": "http://example.org/fhir/Patient/p2/_history/3"}},
        {"entity": {"reference": "#contained"}},
    ],
}


def test_chain_with_reverse_chain(offline_engine):
    # Encounters of patients that are members of Group 102 (FHIR R5 search example)
    search = Search(
        SearchContext(offline_engine, "Encounter"),
        params=(("patient._has:Group:member:_id", "102"),),
    )
    references, asked = drive(
        search.chain(*search.chain_params[0]),
        {
            "Group": [GROUP_102],
            "Patient": [
                {"resourceType": "Patient", "id": "p1"},
                {"resourceType": "Patient", "id": "p2"},
            ],
        },
    )
    # the Group query, then the Patients it refers to
    assert asked == ["Group", "Patient"]
    assert references == ["Patient/p1", "Patient/p2"]
    assert search.chain_reference_name("patient._has:Group:member:_id") == "patient"


def test_chain_with_reverse_chain_without_match(offline_engine):
    search = Search(
        SearchContext(offline_engine, "Encounter"),
        params=(("patient._has:Group:member:_id", "nothing"),),
    )
    references, asked = drive(search.chain(*search.chain_params[0]), {})
    # no source Group -> the Patient query is never sent
    assert asked == ["Group"]
    assert references == []


def test_untyped_chain_with_reverse_chain(offline_engine):
    search = Search(
        SearchContext(offline_engine, "DiagnosticReport"),
        params=(("subject._has:Group:member:_id", "102"),),
    )
    references, asked = drive(
        search.chain(*search.chain_params[0]),
        {"Group": [GROUP_102], "Patient": [{"resourceType": "Patient", "id": "p1"}]},
    )
    # DiagnosticReport.subject -> Group | Device | Patient | Location; Group.member can
    # refer to Group, Device and Patient, but only Patient members exist
    assert asked == ["Group", "Group", "Group", "Patient"]
    assert references == ["Patient/p1"]


def test_chain_with_nested_reverse_chain(offline_engine):
    # Encounters of patients with an Observation audited by a given agent
    search = Search(
        SearchContext(offline_engine, "Encounter"),
        params=(
            (
                "patient._has:Observation:patient:_has:AuditEvent:entity:agent",
                "Practitioner/me",
            ),
        ),
    )
    references, asked = drive(
        search.chain(*search.chain_params[0]),
        {
            "AuditEvent": [
                {
                    "resourceType": "AuditEvent",
                    "id": "a1",
                    "entity": [{"what": {"reference": "Observation/o1"}}],
                }
            ],
            "Observation": [
                {
                    "resourceType": "Observation",
                    "id": "o1",
                    "subject": {"reference": "Patient/p1"},
                }
            ],
            "Patient": [{"resourceType": "Patient", "id": "p1"}],
        },
    )
    assert asked == ["AuditEvent", "Observation", "Patient"]
    assert references == ["Patient/p1"]


def test_chain_through_reverse_chain(offline_engine):
    # Encounters of patients with an Observation performed by a practitioner "Careful"
    search = Search(
        SearchContext(offline_engine, "Encounter"),
        params=(
            ("patient._has:Observation:subject:performer:Practitioner.name", "Careful"),
        ),
    )
    references, asked = drive(
        search.chain(*search.chain_params[0]),
        {
            "Practitioner": [{"resourceType": "Practitioner", "id": "d1"}],
            "Observation": [
                {
                    "resourceType": "Observation",
                    "id": "o1",
                    "subject": {"reference": "Patient/p1"},
                }
            ],
            "Patient": [{"resourceType": "Patient", "id": "p1"}],
        },
    )
    assert asked == ["Practitioner", "Observation", "Patient"]
    assert references == ["Patient/p1"]


def test_chain_with_reverse_chain_errors(offline_engine):
    def resolve(resource_type, name):
        search = Search(
            SearchContext(offline_engine, resource_type), params=((name, "x"),)
        )
        return drive(search.chain(name, "x"), {})

    with raises(
        ValidationError,
        match=re.escape(
            "bad _has param '_has:Group:member', "
            "should be _has:Resource:ref_search_param:value_search_param=value"
        ),
    ):
        resolve("Encounter", "patient._has:Group:member")

    with raises(
        ValidationError,
        match=re.escape(
            "search parameter Group.type must be of type 'reference', got token"
        ),
    ):
        resolve("Encounter", "patient:Patient._has:Group:type:_id")

    with raises(
        ValidationError,
        match=re.escape(
            "invalid reference Group.member (Practitioner,Group,Device,Medication,"
            "Patient,Substance,PractitionerRole) in the current search context "
            "(Location)"
        ),
    ):
        resolve("Observation", "subject:Location._has:Group:member:_id")

    with raises(
        ValidationError,
        match=re.escape(
            "reverse chain '_has:Group:member:_id' cannot refer to any target "
            "of ``Encounter.service-provider`` (Organization)"
        ),
    ):
        resolve("Encounter", "service-provider._has:Group:member:_id")


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


def search_param(engine, resource_type, code):
    return getattr(SearchContext(engine, resource_type).definitions[0], code)


def test_reference_targets(offline_engine):
    # shared "clinical-patient" definition: targets Patient and Group, but the
    # Encounter expression only allows Patient
    patient = search_param(offline_engine, "Encounter", "patient")
    assert patient.target == ["Patient", "Group"]
    assert reference_targets(patient) == ["Patient"]
    # no resolve() restriction -> the declared targets
    subject = search_param(offline_engine, "Encounter", "subject")
    assert reference_targets(subject) == subject.target


def test_extract_references(offline_engine):
    member = search_param(offline_engine, "Group", "member")
    # repeating element in the middle of the path, absolute/versioned and
    # contained references
    assert make_result(GROUP_102).extract_references(member) == {
        "Patient": ["p1", "p2"]
    }

    patient = search_param(offline_engine, "Observation", "patient")
    observations = make_result(
        {"resourceType": "Observation", "subject": {"reference": "Patient/p9"}},
        {"resourceType": "Observation", "subject": {"reference": "Group/g1"}},
        {"resourceType": "Observation", "subject": {"display": "no reference"}},
    )
    # ``where(resolve() is Patient)`` keeps only Patient references
    assert observations.extract_references(patient) == {"Patient": ["p9"]}
