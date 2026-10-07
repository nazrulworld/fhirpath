#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fluent API: fhirpath.FHIRPath over the core engine."""

import datetime
from decimal import Decimal

import pytest

from fhirpath import FHIRPath
from fhirpath.core import EvaluationError, FPDate, FHIRPathSyntaxError, Quantity
from fhirpath.fhirpath import Expr
from tests.core._fixtures import load_json, load_model

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


@pytest.fixture(params=["model", "dict"])
def fp(request):
    loader = load_model if request.param == "model" else load_json
    return FHIRPath(loader("Patient.json"))


def test_navigation(fp):
    assert fp.name.given.to_list() == ["Elector", "Patient", "Sir", "Jonson"]
    assert fp.Patient.name.family.to_list() == ["Saint", "Herbar"]
    assert fp.DomainResource.gender.to_list() == ["male"]
    assert fp["gender"].to_list() == ["male"]
    assert fp.name[1].family.to_list() == ["Herbar"]
    assert fp.name[5].to_list() == []
    assert fp.name[-1].to_list() == []
    assert fp.name.given[1:3].to_list() == ["Patient", "Sir"]
    assert fp.nonExisting.to_list() == []
    assert fp.birthDate.to_list() == [FPDate.parse("1995-12-25")]


def test_functions_and_chaining(fp):
    assert fp.name.where("use = 'official'").given.first().to_list() == ["Sir"]
    assert fp.name.given.count().to_list() == [4]
    assert fp.name.select("given.first() + ' ' + family").to_list() == [
        "Elector Saint",
        "Sir Herbar",
    ]
    assert fp.name.exists("use = 'nickname'").to_list() == [False]
    assert fp.name.all("given.exists()").to_list() == [True]
    assert fp.name.sort("family desc").family.to_list() == ["Saint", "Herbar"]
    assert fp.name.ofType("HumanName").count().to_list() == [2]
    assert fp.iif("active", "'yes'", "'no'").to_list() == ["yes"]
    assert fp.name.aggregate("$total + given.count()", 0).to_list() == [4]


def test_keyword_functions(fp):
    assert fp.gender.is_("code").to_list() == [True]
    assert fp.gender.as_("string").to_list() == []
    assert fp.active.not_().to_list() == [False]


def test_value_arguments(fp):
    given = fp.name.first().given.first()
    assert given.substring(1, 2).to_list() == ["le"]
    assert given.startsWith("Ele").to_list() == [True]
    assert given.replace("E", "e").to_list() == ["elector"]
    assert fp.birthDate.toString().startsWith("1995").to_list() == [True]
    # a Python string is a String value, an Expr is an expression
    assert fp.name.given.combine("x").count().to_list() == [5]
    assert fp.name.given.combine(Expr("name.family")).to_list()[-2:] == [
        "Saint",
        "Herbar",
    ]
    # another FHIRPath and Python lists are passed as collections
    assert fp.name.given.intersect(fp.name.first().given).to_list() == [
        "Elector",
        "Patient",
    ]
    assert fp.name.given.exclude(["Sir", "Jonson"]).to_list() == ["Elector", "Patient"]
    assert FHIRPath(None).iif(True, "1", "2").to_list() == [1]


@pytest.mark.parametrize(
    "value,expected",
    [
        (1.5, Decimal("1.5")),
        (Decimal("1.50"), Decimal("1.50")),
        (datetime.date(2020, 1, 2), FPDate.parse("2020-01-02")),
        (Quantity(5, "mg"), Quantity(5, "mg")),
        (None, None),
    ],
)
def test_python_literals(value, expected):
    combined = FHIRPath(None).combine(value).to_list()
    assert combined == ([] if expected is None else [expected])


def test_define_variable_chain(fp):
    assert fp.defineVariable("g", "gender").name.select("%g").to_list() == [
        "male",
        "male",
    ]
    with pytest.raises(EvaluationError):
        fp.defineVariable("g", "gender").defineVariable("g")


def test_variables_and_options():
    patient = {
        "resourceType": "Patient",
        "managingOrganization": {"reference": "Organization/1"},
    }
    org = {"resourceType": "Organization", "id": "1", "name": "ACME"}
    fp = FHIRPath(patient, {"limit": 2}, resolver=lambda ref, origin: org)
    assert fp.evaluate("%limit + 1").to_list() == [3]
    assert fp.managingOrganization.resolve().name.to_list() == ["ACME"]


def test_evaluate_uses_the_collection_as_input(fp):
    assert fp.name.evaluate("where(use = 'usual').text").to_list() == ["Patient Saint"]
    assert fp.name.evaluate("$this.count()").to_list() == [2]


def test_output_protocols(fp):
    assert list(fp.name.given) == fp.name.given.to_list()
    assert len(fp.name) == 2
    assert bool(fp.active) is True
    assert bool(fp.name.exists("use = 'nickname'")) is False
    assert bool(fp.name) is True
    assert bool(fp.deceased) is False
    assert repr(fp.gender) == "FHIRPath(['male'])"
    nodes = fp.name.to_nodes()
    assert [node.type_name for node in nodes] == ["HumanName", "HumanName"]
    assert fp.name.type().name.to_list() == ["HumanName", "HumanName"]


def test_immutability_and_errors(fp):
    with pytest.raises(TypeError):
        fp.name = "x"
    with pytest.raises(TypeError):
        fp()
    with pytest.raises(AttributeError):
        fp.name.noSuchFunction()
    with pytest.raises(FHIRPathSyntaxError):
        fp.name.where("use = ")
    with pytest.raises(TypeError):
        fp.name.sort(1)
    with pytest.raises(EvaluationError):
        fp.name.given.substring(1)  # more than one input item
    with pytest.raises(AttributeError):
        fp._private


def test_dir_lists_functions(fp):
    names = dir(fp)
    assert "where" in names and "is_" in names and "to_list" in names
