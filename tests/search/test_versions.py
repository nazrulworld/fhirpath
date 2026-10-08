# _*_ coding: utf-8 _*_
"""Search on every supported FHIR release (STU3, R4, R4B, R5), without a search
backend: SearchParameter expressions, definition files and the FQL terms built
for each release."""

import io
import json
import zipfile

import pytest
from pytest import raises

from fhirpath.enums import FHIR_VERSION
from fhirpath.search.dialects.elasticsearch import ElasticSearchDialect
from fhirpath.search.engine.es import ElasticsearchEngine
from fhirpath.search.fhirspec import SPEC_JSON_DIR
from fhirpath.search.fhirspec.downloader import (
    extract_spec_files,
    minify_profiles,
    minify_valuesets,
)
from fhirpath.search.fhirspec.expression import (
    UnsupportedExpression,
    component_paths,
    element_paths,
    split_by_base,
    to_expression,
)
from fhirpath.core.parser import parse
from fhirpath.search.interfaces import IGroupTerm
from fhirpath.search.search import Search, SearchContext

from .._utils import has_internet_connection

RELEASES = ("STU3", "R4", "R4B", "R5")


# ------------------------------------------------------------------ expressions


@pytest.mark.parametrize(
    "expression,paths",
    [
        ("Patient.name", ["Patient.name"]),
        # R5
        (
            "Observation.value.ofType(Quantity) | Observation.value.ofType(SampledData)",
            ["Observation.valueQuantity", "Observation.valueSampledData"],
        ),
        # R4 / R4B
        ("(Condition.abatement as Age)", ["Condition.abatementAge"]),
        # STU3
        ("Condition.abatement.as(dateTime)", ["Condition.abatementDateTime"]),
        (
            "Observation.subject.where(resolve() is Patient)",
            ["Observation.subject.where(resolve() is Patient)"],
        ),
        (
            "Patient.telecom.where(system='phone')",
            ["Patient.telecom.where(system='phone')"],
        ),
        # first() narrows: searching all values is a superset
        (
            "(Appointment.start | Appointment.requestedPeriod.start).first()",
            ["Appointment.start", "Appointment.requestedPeriod.start"],
        ),
        # computed branches are left out when another branch is a path
        (
            "(Patient.deceased.exists() and Patient.deceased != false) | Patient.name",
            ["Patient.name"],
        ),
    ],
)
def test_element_paths(expression, paths):
    assert element_paths(expression) == paths


@pytest.mark.parametrize(
    "expression",
    [
        "Patient.deceased.exists() and (Patient.deceased != false)",
        "ActivityDefinition.relatedArtifact.where(type = 'composed-of').resource",
        "Location.extension('http://example.org/geojson').value",
    ],
)
def test_element_paths_unsupported(expression):
    with raises(UnsupportedExpression):
        element_paths(expression)


def test_to_expression_roundtrip():
    for expression in (
        "Patient.telecom.where(system = 'phone') | Patient.name.given",
        "(Observation.value as Quantity) | Observation.component.value.ofType(Quantity)",
        "Bundle.entry[0].resource as Composition",
        "Patient.deceased.exists() and (Patient.deceased != false)",
        r"Patient.name.where(text = 'it\'s').given",
    ):
        tree = parse(expression)
        assert parse(to_expression(tree)) == tree


def test_split_by_base():
    assert split_by_base("Patient.name | Practitioner.name", ["Patient"]) == {
        "Patient": "Patient.name | Practitioner.name"
    }
    assert split_by_base(
        "(Patient.name.given) | Practitioner.name.given | Patient.name.family",
        ["Patient", "Practitioner"],
    ) == {
        "Patient": "Patient.name.given | Patient.name.family",
        "Practitioner": "Practitioner.name.given",
    }


def test_split_by_base_anchors_relative_branch():
    # R5 clinical-date: the Appointment branch has no resource name, and
    # CareTeam has no branch at all
    expression = (
        "AllergyIntolerance.recordedDate | (start | requestedPeriod.start).first() "
        "| AuditEvent.recorded"
    )
    bases = ["AllergyIntolerance", "Appointment", "AuditEvent", "CareTeam"]
    assert split_by_base(expression, bases) == {
        "AllergyIntolerance": "AllergyIntolerance.recordedDate",
        "Appointment": "(Appointment.start | Appointment.requestedPeriod.start).first()",
        "AuditEvent": "AuditEvent.recorded",
    }


def test_component_paths():
    assert component_paths(
        "Group.characteristic", "(value as CodeableConcept) | (value as boolean)"
    ) == [
        "Group.characteristic.valueCodeableConcept",
        "Group.characteristic.valueBoolean",
    ]
    assert component_paths("Observation", "value.ofType(Quantity)") == [
        "Observation.valueQuantity"
    ]
    # %resource is the resource the composite starts at
    assert component_paths(
        "MolecularSequence.variant", "%resource.referenceSeq.chromosome"
    ) == ["MolecularSequence.referenceSeq.chromosome"]


# ------------------------------------------------------------- definition files


def bundle(*resources):
    return {
        "resourceType": "Bundle",
        "entry": [
            {"fullUrl": "http://hl7.org/fhir/%s" % r["id"], "resource": r}
            for r in resources
        ],
    }


def test_minify():
    profiles = bundle(
        {
            "resourceType": "StructureDefinition",
            "id": "Patient",
            "text": {"div": "..."},
            "snapshot": {"element": []},
            "differential": {"element": [{"path": "Patient"}]},
        },
        {"resourceType": "OperationDefinition", "id": "everything"},
    )
    minified = minify_profiles(profiles)
    assert [e["resource"]["id"] for e in minified["entry"]] == ["Patient"]
    assert sorted(minified["entry"][0]["resource"]) == [
        "differential",
        "id",
        "resourceType",
    ]

    valuesets = bundle({"resourceType": "ValueSet", "id": "vs", "text": {}, "url": "u"})
    assert minify_valuesets(valuesets)["entry"][0]["resource"] == {
        "resourceType": "ValueSet",
        "id": "vs",
        "url": "u",
    }


def make_archive(folder="", version_info=True):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for name in (
            "search-parameters.json",
            "profiles-resources.json",
            "profiles-types.json",
            "valuesets.json",
        ):
            archive.writestr(folder + name, json.dumps(bundle()))
        if version_info:
            archive.writestr(folder + "version.info", "[FHIR]\nversion=4.3.0\n")
    return data


@pytest.mark.parametrize(
    "release,folder,version_info",
    [("R4B", "definitions.json/", True), ("STU3", "", False)],
)
def test_extract_spec_files(tmp_path, release, folder, version_info):
    archive = tmp_path / "definitions.json.zip"
    archive.write_bytes(make_archive(folder, version_info).getvalue())
    release = FHIR_VERSION[release]

    extract_spec_files(tmp_path, archive, release)

    target = tmp_path / release.value
    assert sorted(p.name for p in target.iterdir()) == [
        "profiles-resources.min.json",
        "profiles-types.min.json",
        "search-parameters.json",
        "valuesets.min.json",
        "version.info",
    ]
    info = (target / "version.info").read_text()
    if version_info:
        assert info == "[FHIR]\nversion=4.3.0\n"
    else:
        # the STU3 archive has none: the official build's
        assert "FhirVersion=3.0.2.11917" in info
    # no work folder left behind
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        ["definitions.json.zip", release.value]
    )


def test_extract_spec_files_incomplete_archive(tmp_path):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("search-parameters.json", "{}")
    archive_file = tmp_path / "definitions.json.zip"
    archive_file.write_bytes(data.getvalue())

    with raises(FileNotFoundError, match="misses profiles-resources.json"):
        extract_spec_files(tmp_path, archive_file, FHIR_VERSION.R5)
    assert not (tmp_path / FHIR_VERSION.R5.value).exists()


# ------------------------------------------------------------- query building


def spec_available(release_name):
    release = FHIR_VERSION[release_name]
    return (SPEC_JSON_DIR / release.name / release.value).exists()


@pytest.fixture(params=RELEASES)
def release_engine(request):
    if not spec_available(request.param) and not has_internet_connection():
        pytest.skip("FHIR definitions are downloaded on first use")
    release = FHIR_VERSION[request.param]

    class Engine(ElasticsearchEngine):
        def __init__(self):
            super().__init__(
                release, lambda x: None, lambda x: ElasticSearchDialect(None)
            )

    return Engine()


def where_terms(engine, resource_type, *params):
    search = Search(SearchContext(engine, resource_type), params=params)
    query_result = search.build()
    return list(query_result._query.get_where())


def flatten(term):
    """(path, operator, value) of every leaf term."""
    if IGroupTerm.providedBy(term):
        return [leaf for t in term.terms for leaf in flatten(t)]
    value = getattr(term, "value", None)
    raw = value.value if value is not None else None
    return [(str(term.path), term.comparison_operator.name, str(raw))]


def leaves(engine, resource_type, *params):
    return [
        leaf for t in where_terms(engine, resource_type, *params) for leaf in flatten(t)
    ]


def test_basic_parameters_on_every_release(release_engine):
    engine = release_engine
    assert ("Patient.gender", "eq", "male") in leaves(
        engine, "Patient", ("gender", "male")
    )
    assert ("Patient.birthDate", "ge", "2000-01-01") in leaves(
        engine, "Patient", ("birthdate", "ge2000-01-01")
    )
    identifier = leaves(engine, "Patient", ("identifier", "http://acme.org|123"))
    assert ("Patient.identifier.system", "eq", "http://acme.org") in identifier
    assert ("Patient.identifier.value", "eq", "123") in identifier
    assert ("Observation.code.coding.code", "eq", "1234-5") in leaves(
        engine, "Observation", ("code", "http://loinc.org|1234-5")
    )


def test_choice_element_on_every_release(release_engine):
    # R5: Observation.value.ofType(Quantity), R4/R4B: (Observation.value as Quantity),
    # STU3: Observation.value.as(Quantity)
    found = leaves(
        release_engine,
        "Observation",
        ("value-quantity", "ge5.4|http://unitsofmeasure.org|mg"),
    )
    assert ("Observation.valueQuantity.value", "ge", "5.4") in found
    assert ("Observation.valueQuantity.code", "eq", "mg") in found


def test_untyped_choice_element_expands(release_engine):
    # Observation.date is "Observation.effective" (STU3-R4B) or the typed
    # alternatives (R5): every typed element of the choice is searched
    (term,) = where_terms(release_engine, "Observation", ("date", "2020-01-01"))
    assert IGroupTerm.providedBy(term)
    paths = {path.split(".")[1] for path, _, _ in flatten(term)}
    assert {"effectiveDateTime", "effectivePeriod"} <= paths


def test_multiple_paths_or(release_engine):
    # the parameter matches when any of its elements matches
    (term,) = where_terms(release_engine, "Patient", ("address-city", "Oslo"))
    assert [path for path, _, _ in flatten(term)] == ["Patient.address.city"]

    (term,) = where_terms(release_engine, "Organization", ("name", "Acme"))
    paths = sorted(path for path, _, _ in flatten(term))
    assert paths == ["Organization.alias", "Organization.name"]


def test_composite_on_every_release(release_engine):
    found = leaves(
        release_engine,
        "Observation",
        ("code-value-quantity", "http://loinc.org|8480-6$ge150"),
    )
    assert ("Observation.code.coding.code", "eq", "8480-6") in found
    # the value component is parsed as a quantity, with its prefix
    assert ("Observation.valueQuantity.value", "ge", "150") in found


@pytest.mark.parametrize(
    "code,value,path",
    [
        (
            "contraindication",
            "http://snomed.info/sct|123",
            "ClinicalUseDefinition.contraindication.diseaseSymptomProcedure.concept"
            ".coding.code",
        ),
        (
            "contraindication-reference",
            "Condition/1",
            "ClinicalUseDefinition.contraindication.diseaseSymptomProcedure.reference"
            ".reference",
        ),
    ],
)
def test_codeable_reference_r4b(code, value, path):
    if not spec_available("R4B") and not has_internet_connection():
        pytest.skip("FHIR definitions are downloaded on first use")

    class Engine(ElasticsearchEngine):
        def __init__(self):
            super().__init__(
                FHIR_VERSION.R4B, lambda x: None, lambda x: ElasticSearchDialect(None)
            )

    found = leaves(Engine(), "ClinicalUseDefinition", (code, value))
    assert path in [p for p, _, _ in found]


def test_special_processing_is_not_supported():
    if not spec_available("R5") and not has_internet_connection():
        pytest.skip("FHIR definitions are downloaded on first use")

    class Engine(ElasticsearchEngine):
        def __init__(self):
            super().__init__(
                FHIR_VERSION.R5, lambda x: None, lambda x: ElasticSearchDialect(None)
            )

    with raises(NotImplementedError, match="needs special processing"):
        where_terms(Engine(), "Location", ("near", "42.25|-83.69|10|km"))
