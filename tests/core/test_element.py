# _*_ coding: utf-8 _*_
"""Navigation over FHIR data (models and dicts) and the public API."""

from decimal import Decimal

import pytest

from fhirpath.core import (
    CompiledExpression,
    Element,
    EvaluationError,
    FPDate,
    Quantity,
    compile,
    evaluate,
)
from fhirpath.core.model import Node
from tests.core._fixtures import load_json, load_model

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


@pytest.fixture(params=["model", "dict"])
def patient(request):
    if request.param == "model":
        return load_model("Patient.json")
    return load_json("Patient.json")


def test_element_query(patient):
    el = Element(patient)
    assert len(el.query("name")) == 2
    assert len(el.query("name[0]")) == 1
    assert el.query("name[0].given") == ["Elector", "Patient"]
    assert el.query("Patient.name.given.count()") == [4]


def test_element_where_filter(patient):
    el = Element(patient)
    assert len(el.query("name.where(use = 'official')")) == 1
    assert len(el.query("name.where(use = 'usual' or family = 'Herbar')")) == 2
    assert len(el.query("name.where(use = 'usual' and family = 'Herbar')")) == 0
    assert el.query("name.where(use = 'usual' and given[0] = 'Elector').family") == [
        "Saint"
    ]
    assert el.query(
        "name.where(use = 'official' and given[0] != 'Elector').given.first()"
    ) == ["Sir"]


def test_element_test_predicate(patient):
    el = Element(patient)
    assert el.test("active")
    assert el.test("name.exists()")
    assert not el.test("deceased.exists()")
    assert not el.test("name.where(use = 'nickname')")


def test_primitive_values_are_system_values(patient):
    assert evaluate(patient, "birthDate") == [FPDate.parse("1995-12-25")]
    assert evaluate(patient, "active") == [True]
    assert evaluate(patient, "birthDate < @2000") == [True]


def test_complex_results_keep_the_original_value():
    patient = load_model("Patient.json")
    names = evaluate(patient, "name.where(use = 'official')")
    assert names == [patient.name[1]]
    nodes = evaluate(patient, "name", nodes=True)
    assert all(isinstance(n, Node) and n.type_name == "HumanName" for n in nodes)


def test_root_type_name_filters():
    patient = load_json("Patient.json")
    assert evaluate(patient, "Patient.gender") == ["male"]
    assert evaluate(patient, "DomainResource.gender") == ["male"]
    assert evaluate(patient, "Observation.status") == []


def test_choice_elements():
    observation = {
        "resourceType": "Observation",
        "status": "final",
        "code": {"text": "weight"},
        "valueQuantity": {
            "value": Decimal("185"),
            "unit": "lbs",
            "system": "http://unitsofmeasure.org",
            "code": "[lb_av]",
        },
    }
    assert evaluate(observation, "Observation.value.unit") == ["lbs"]
    assert evaluate(observation, "Observation.value.is(Quantity)") == [True]
    assert evaluate(observation, "Observation.value.ofType(Period)") == []
    assert evaluate(observation, "Observation.value > 80 'kg'") == [True]
    assert evaluate(observation, "Observation.value.as(Quantity).code") == ["[lb_av]"]


def test_primitive_extensions():
    patient = {
        "resourceType": "Patient",
        "birthDate": "1974-12-25",
        "_birthDate": {
            "extension": [
                {
                    "url": "http://hl7.org/fhir/StructureDefinition/patient-birthTime",
                    "valueDateTime": "1974-12-25T14:35:45-05:00",
                }
            ]
        },
        "name": [
            {
                "given": ["Jim", None],
                "_given": [None, {"extension": [{"url": "x", "valueString": "y"}]}],
            }
        ],
    }
    url = "http://hl7.org/fhir/StructureDefinition/patient-birthTime"
    assert evaluate(patient, "birthDate.extension('%s').exists()" % url) == [True]
    assert evaluate(patient, "birthDate.extension(%`ext-patient-birthTime`).value") == [
        evaluate(None, "@1974-12-25T14:35:45-05:00")[0]
    ]
    # a primitive that only has extensions is a node without a value
    assert evaluate(patient, "name.given.count()") == [2]
    assert evaluate(patient, "name.given[1].hasValue()") == [False]
    assert evaluate(patient, "name.given[0].hasValue()") == [True]
    assert evaluate(patient, "name.given") == ["Jim"]


def test_resolve_contained_and_bundle():
    patient = {
        "resourceType": "Patient",
        "contained": [{"resourceType": "Practitioner", "id": "p1", "active": True}],
        "generalPractitioner": [{"reference": "#p1"}],
    }
    assert evaluate(patient, "generalPractitioner.resolve().active") == [True]
    assert evaluate(patient, "generalPractitioner.all(resolve() is Practitioner)") == [
        True
    ]
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "fullUrl": "http://x/Patient/1",
                "resource": {"resourceType": "Patient", "id": "1", "gender": "female"},
            },
            {
                "fullUrl": "http://x/Observation/2",
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"text": "x"},
                    "subject": {"reference": "Patient/1"},
                },
            },
        ],
    }
    assert evaluate(
        bundle, "entry.resource.ofType(Observation).subject.resolve().gender"
    ) == ["female"]


def test_resolver_hook():
    target = {"resourceType": "Organization", "id": "o1", "name": "ACME"}
    patient = {
        "resourceType": "Patient",
        "managingOrganization": {"reference": "Organization/o1"},
    }
    resolver = lambda reference, origin: (
        target if reference == "Organization/o1" else None
    )  # noqa: E731
    assert evaluate(
        patient, "managingOrganization.resolve().name", resolver=resolver
    ) == ["ACME"]


def test_environment_variables(patient):
    assert evaluate(patient, "%resource.gender") == ["male"]
    assert evaluate(patient, "%context.id") == evaluate(patient, "id")
    assert evaluate(patient, "%ucum") == ["http://unitsofmeasure.org"]
    assert evaluate(patient, "%`vs-administrative-gender`") == [
        "http://hl7.org/fhir/ValueSet/administrative-gender"
    ]
    assert evaluate(patient, "%limit + 1", {"limit": 2}) == [3]
    assert evaluate(patient, "%unset.empty()", {"unset": None}) == [True]
    with pytest.raises(EvaluationError):
        evaluate(patient, "%undefined")


def test_contained_root_resource():
    patient = {
        "resourceType": "Patient",
        "id": "outer",
        "contained": [
            {
                "resourceType": "Observation",
                "id": "inner",
                "status": "final",
                "code": {"text": "x"},
            }
        ],
    }
    assert evaluate(patient, "contained.select(%rootResource.id)") == ["outer"]


def test_compile_reuse_and_errors():
    expression = compile("name.given.first()")
    assert isinstance(expression, CompiledExpression)
    assert expression.evaluate(load_json("Patient.json")) == ["Elector"]
    assert expression.evaluate(None) == []
    with pytest.raises(EvaluationError) as info:
        evaluate(load_json("Patient.json"), "name.given + 'x'")
    assert "single item" in str(info.value)


def test_quantity_output():
    (result,) = evaluate(None, "2 'mg' * 3")
    assert isinstance(result, Quantity)
    assert (result.value, result.unit) == (Decimal(6), "mg")
