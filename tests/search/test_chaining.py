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
    # each reference also matches its absolute and versioned forms
    assert [[alt["bool"]["should"] for alt in alts] for alts in should] == [
        [
            [
                {"term": {"observation_resource.subject.reference": f"Patient/{i}"}},
                {
                    "term": {
                        "observation_resource.subject.reference": (
                            f"http://nohost/@fhir/Patient/{i}"
                        )
                    }
                },
                {
                    "prefix": {
                        "observation_resource.subject.reference": {
                            "value": f"Patient/{i}/_history/"
                        }
                    }
                },
            ]
            for i in ("p1", "p2")
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


# ---------------------------------------------------------- top-level _has


def has_search(engine, resource_type, *params):
    return Search(SearchContext(engine, resource_type), params=params)


AUDITED_OBSERVATION = {
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
}


def test_reverse_chain(offline_engine):
    search = has_search(
        offline_engine, "Patient", ("_has:Observation:patient:code", "1234-5")
    )
    results, asked = drive(search.reverse_chains(), AUDITED_OBSERVATION)
    assert asked == ["Observation"]
    assert results == {"Patient": {"p1"}}


def test_nested_reverse_chain(offline_engine):
    # FHIR R5 search example: patients with an observation audited by a user
    search = has_search(
        offline_engine,
        "Patient",
        ("_has:Observation:patient:_has:AuditEvent:entity:agent", "Practitioner/me"),
    )
    results, asked = drive(search.reverse_chains(), AUDITED_OBSERVATION)
    # innermost first: the audit events, then the observations they refer to
    assert asked == ["AuditEvent", "Observation"]
    assert results == {"Patient": {"p1"}}


def test_chain_after_reverse_chain(offline_engine):
    search = has_search(
        offline_engine,
        "Patient",
        ("_has:Observation:subject:performer:Practitioner.name", "Careful"),
    )
    results, asked = drive(
        search.reverse_chains(),
        {
            "Practitioner": [{"resourceType": "Practitioner", "id": "d1"}],
            **AUDITED_OBSERVATION,
        },
    )
    assert asked == ["Practitioner", "Observation"]
    assert results == {"Patient": {"p1"}}


def test_reverse_chains_are_anded(offline_engine):
    search = has_search(
        offline_engine,
        "Patient",
        ("_has:Observation:patient:code", "1234-5"),  # p1
        ("_has:Group:member:_id", "102"),  # p1, p2
    )
    results, _ = drive(
        search.reverse_chains(), {**AUDITED_OBSERVATION, "Group": [GROUP_102]}
    )
    assert results == {"Patient": {"p1"}}


def test_reverse_chains_without_common_match(offline_engine):
    # an empty intersection stays empty, whatever comes next
    search = has_search(
        offline_engine,
        "Patient",
        ("_has:Observation:patient:code", "1234-5"),  # p1
        ("_has:Group:member:_id", "102"),  # p1, p2
        ("_has:Observation:patient:code", "nothing"),
    )
    answers = {**AUDITED_OBSERVATION, "Group": [GROUP_102]}
    asked = []

    def answer(resolver):
        try:
            query = next(resolver)
            while True:
                (resource_type,) = resource_types(query)
                asked.append(resource_type)
                # the third _has (second Observation query) matches nothing
                resources = answers.get(resource_type, [])
                if resource_type == "Observation" and asked.count("Observation") > 1:
                    resources = []
                query = resolver.send(make_result(*resources))
        except StopIteration as stop:
            return stop.value

    assert answer(search.reverse_chains()) == {}
    assert asked == ["Observation", "Group", "Observation"]


def test_reverse_chain_empty_value_is_ignored(offline_engine):
    search = has_search(
        offline_engine, "Patient", ("_has:Observation:patient:code", "")
    )
    assert "_has" not in search.result_params


def test_reverse_chain_with_several_resource_types(offline_engine):
    # Group.member refers to Patients and Practitioners
    group = dict(
        GROUP_102,
        member=GROUP_102["member"] + [{"entity": {"reference": "Practitioner/d1"}}],
    )
    search = has_search(
        offline_engine,
        "Patient",
        ("_type", "Practitioner"),
        ("_has:Group:member:_id", "102"),
    )
    results, asked = drive(search.reverse_chains(), {"Group": [group]})
    assert asked == ["Group", "Group"]
    assert results == {"Patient": {"p1", "p2"}, "Practitioner": {"d1"}}

    # a resource matches the ids of its own type
    search.reverse_chaining_results = results
    terms = list(search.build()._query.get_where())
    ors = [t for t in terms if getattr(t, "terms", None) and len(t.terms) == 2]
    assert [str(t.path) for t in ors[0].terms] == ["Patient.id", "Practitioner.id"]


def test_reverse_chain_errors(offline_engine):
    def resolve(resource_type, name):
        search = has_search(offline_engine, resource_type, (name, "x"))
        return drive(search.reverse_chains(), {})

    with raises(
        ValidationError,
        match=re.escape(
            "bad _has param '_has:Observation:patient', "
            "should be _has:Resource:ref_search_param:value_search_param=value"
        ),
    ):
        resolve("Patient", "_has:Observation:patient")

    with raises(
        ValidationError,
        match=re.escape(
            "search parameter Observation.category must be "
            "of type 'reference', got token"
        ),
    ):
        resolve("Patient", "_has:Observation:category:code")

    with raises(
        ValidationError,
        match=re.escape(
            "No search definition is available for search "
            "parameter ``unknown`` on Resource ``Observation``."
        ),
    ):
        resolve("Patient", "_has:Observation:unknown:code")

    with raises(
        ValidationError,
        match=re.escape(
            "invalid reference Observation.encounter (Encounter,EpisodeOfCare) "
            "in the current search context (Patient)"
        ),
    ):
        resolve("Patient", "_has:Observation:encounter:identifier")


def test_search_with_nested_reverse_chain(offline_engine, monkeypatch):
    executed = []

    def fetchall(query_result):
        (resource_type,) = resource_types(query_result)
        executed.append(resource_type)
        if resource_type == "Patient":
            return make_result({"resourceType": "Patient", "id": "p1"})
        return make_result(*AUDITED_OBSERVATION[resource_type])

    monkeypatch.setattr(QueryResult, "fetchall", fetchall)

    search = has_search(
        offline_engine,
        "Patient",
        ("_has:Observation:patient:_has:AuditEvent:entity:agent", "Practitioner/me"),
    )
    bundle = search()
    assert executed == ["AuditEvent", "Observation", "Patient"]
    assert search.reverse_chaining_results == {"Patient": {"p1"}}
    assert bundle.total == 1


@pytest.mark.asyncio
async def test_async_search_with_unsatisfied_reverse_chain_is_empty(
    offline_engine, monkeypatch
):
    async def fetchall(query_result):
        return make_result()

    monkeypatch.setattr(QueryResult, "fetchall", fetchall)

    search = AsyncSearch(
        SearchContext(offline_engine, "Patient"),
        params=(("_has:Observation:patient:_has:AuditEvent:entity:agent", "x"),),
    )
    bundle = await search()
    assert bundle.total == 0


def test_reverse_chain_needs_a_resource_type(offline_engine):
    search = Search(
        SearchContext(offline_engine, None),
        params=(("_has:Observation:patient:code", "1234-5"),),
    )
    with raises(ValidationError, match="needs a resource type"):
        drive(search.reverse_chains(), {})


# ------------------------------------------------- reference hierarchies


LOCATIONS = {
    # building <- floor <- room
    "building": None,
    "floor": "building",
    "room": "floor",
    "elsewhere": None,
}


def location(id_):
    resource = {"resourceType": "Location", "id": id_}
    if LOCATIONS[id_]:
        resource["partOf"] = {"reference": f"Location/{LOCATIONS[id_]}"}
    return resource


def walk_terms(terms):
    for term in terms:
        if hasattr(term, "terms"):
            yield from walk_terms(term.terms)
        else:
            yield term


def searched(query_result):
    """(paths, values) of the leaf terms of a query."""
    leaves = list(walk_terms(query_result._query.get_where()))
    paths = [str(t.path) for t in leaves]
    values = [str(t.value.raw) for t in leaves if getattr(t, "value", None) is not None]
    return paths, values


def location_answers(query_result):
    """Children (``partof=…``) or the locations themselves (``_id=…``)."""
    paths, values = searched(query_result)
    if any(p.endswith("partOf.reference") for p in paths):
        parents = {v.split("/")[-1] for v in values if v.startswith("Location/")}
        return make_result(
            *[location(i) for i, parent in LOCATIONS.items() if parent in parents]
        )
    return make_result(*[location(i) for i in LOCATIONS if i in values])


def answer_all(resolver, answer):
    """Drive a resolver, answering every sub-query with ``answer(query)``."""
    try:
        query = next(resolver)
        while True:
            query = resolver.send(answer(query))
    except StopIteration as stop:
        return stop.value


def test_reference_below_follows_the_hierarchy(offline_engine):
    search = Search(
        SearchContext(offline_engine, "Encounter"),
        params=(("location:below", "Location/building"),),
    )
    references = answer_all(
        search.resolve_hierarchy("location:below"), location_answers
    )
    assert references == ["Location/building", "Location/floor", "Location/room"]


def test_reference_above_follows_the_hierarchy(offline_engine):
    search = Search(
        SearchContext(offline_engine, "Encounter"),
        params=(("location:above", "room"),),
    )
    references = answer_all(
        search.resolve_hierarchy("location:above"), location_answers
    )
    assert references == ["Location/room", "Location/floor", "Location/building"]


def test_hierarchy_search_is_applied(offline_engine, monkeypatch):
    def fetchall(query_result):
        if resource_types(query_result) == ["Location"]:
            return location_answers(query_result)
        return make_result()

    monkeypatch.setattr(QueryResult, "fetchall", fetchall)
    search = Search(
        SearchContext(offline_engine, "Encounter"),
        params=(("location:below", "Location/floor"),),
    )
    search()
    assert search.hierarchy_references == {
        "location:below": ["Location/floor", "Location/room"]
    }


# ------------------------------------------------------------- includes


STORE = [
    {
        "resourceType": "MedicationDispense",
        "id": "md1",
        "authorizingPrescription": [{"reference": "MedicationRequest/mr1"}],
    },
    {
        "resourceType": "MedicationRequest",
        "id": "mr1",
        "requester": {"reference": "Practitioner/pr1"},
        "subject": {"reference": "Patient/p1"},
    },
    {"resourceType": "Practitioner", "id": "pr1"},
    {"resourceType": "Patient", "id": "p1"},
    {
        "resourceType": "Observation",
        "id": "o1",
        "subject": {"reference": "Patient/p1"},
        "hasMember": [{"reference": "Observation/o2"}],
    },
    {
        "resourceType": "Observation",
        "id": "o2",
        "subject": {"reference": "Patient/p1"},
        "hasMember": [{"reference": "Observation/o3"}],
    },
    {"resourceType": "Observation", "id": "o3", "subject": {"reference": "Patient/p1"}},
]


def _references(resource):
    for value in resource.values():
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, dict) and "reference" in item:
                yield item["reference"]


def store_answers(query_result):
    """Answer ``_id`` and reference queries from ``STORE``."""
    types = resource_types(query_result)
    paths, values = searched(query_result)
    found = []
    for resource in STORE:
        if resource["resourceType"] not in types:
            continue
        if any(p.endswith(".id") for p in paths):
            if resource["id"] in values:
                found.append(resource)
        elif any(reference in values for reference in _references(resource)):
            found.append(resource)
    return make_result(*found)


def included(search, *matches):
    results = answer_all(search.resolve_includes(make_result(*matches)), store_answers)
    return [(row[0]["resourceType"], row[0]["id"]) for r in results for row in r.body]


def test_include_iterate(offline_engine):
    md1 = STORE[0]
    search = Search(
        SearchContext(offline_engine, "MedicationDispense"),
        params=(
            ("_include", "MedicationDispense:prescription"),
            ("_include:iterate", "MedicationRequest:requester"),
        ),
    )
    assert included(search, md1) == [
        ("MedicationRequest", "mr1"),
        ("Practitioner", "pr1"),
    ]

    # without :iterate, the include of MedicationRequest does not apply to
    # included resources
    search = Search(
        SearchContext(offline_engine, "MedicationDispense"),
        params=(
            ("_include", "MedicationDispense:prescription"),
            ("_include", "MedicationRequest:requester"),
        ),
    )
    assert included(search, md1) == [("MedicationRequest", "mr1")]


def test_include_iterate_on_a_circular_reference(offline_engine):
    search = Search(
        SearchContext(offline_engine, "Observation"),
        params=(("_include:iterate", "Observation:has-member"),),
    )
    assert included(search, STORE[4]) == [("Observation", "o2"), ("Observation", "o3")]


def test_stu3_recurse_is_iterate(offline_engine):
    search = Search(
        SearchContext(offline_engine, "Observation"),
        params=(("_include:recurse", "Observation:has-member"),),
    )
    assert search.result_params["_include"] == [("Observation:has-member", True)]


def test_include_wildcards(offline_engine):
    # Source:* follows every reference parameter of the source
    search = Search(
        SearchContext(offline_engine, "MedicationRequest"),
        params=(("_include", "MedicationRequest:*"),),
    )
    assert sorted(included(search, STORE[1])) == [
        ("Patient", "p1"),
        ("Practitioner", "pr1"),
    ]
    # * : everything
    search = Search(
        SearchContext(offline_engine, "MedicationRequest"),
        params=(("_include", "*"),),
    )
    assert sorted(included(search, STORE[1])) == [
        ("Patient", "p1"),
        ("Practitioner", "pr1"),
    ]


def test_matches_are_not_included_again(offline_engine):
    search = Search(
        SearchContext(offline_engine, "Observation"),
        params=(("_include", "Observation:has-member"),),
    )
    # o2 is a match itself: only o3 is included
    assert included(search, STORE[4], STORE[5]) == [("Observation", "o3")]


def test_revinclude_searches_typed_references(offline_engine):
    search = Search(
        SearchContext(offline_engine, "Patient"),
        params=(("_revinclude", "MedicationRequest:subject"),),
    )
    (query,) = search.include_queries_for(
        search.include_specs()[0], make_result(STORE[3]).body, set()
    )
    values = [
        str(t.value.raw)
        for t in walk_terms(query._query.get_where())
        if getattr(t, "value", None) is not None
    ]
    assert "Patient/p1" in values


def test_includes_are_not_capped(offline_engine):
    search = Search(
        SearchContext(offline_engine, "MedicationDispense"),
        params=(("_include", "MedicationDispense:prescription"),),
    )
    (query,) = search.include_queries_for(
        search.include_specs()[0], make_result(STORE[0]).body, set()
    )
    assert query._query.get_limit().empty


# --------------------------------------------------- reference equivalence


def test_ambiguous_plain_id(offline_engine):
    search = Search(
        SearchContext(offline_engine, "Observation"), params=(("subject", "23"),)
    )
    search.build()
    issues = search.outcome_issues()
    assert any("ambiguous" in issue["diagnostics"] for issue in issues)

    search = Search(
        SearchContext(offline_engine, "Observation"),
        params=(("subject", "23"),),
        handling="strict",
    )
    with raises(ValidationError, match="ambiguous"):
        search.build()

    # restricted by the parameter: not ambiguous
    search = Search(
        SearchContext(offline_engine, "Observation"), params=(("patient", "23"),)
    )
    search.build()
    assert search.outcome_issues() == []
