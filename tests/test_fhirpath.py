#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

import pytest

from fhirpath import fhirpath
from fhirpath.enums import FHIR_VERSION
from fhirpath.utils import lookup_fhir_class

from ._utils import FHIR_EXAMPLE_RESOURCES


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


def test_fhirpath_class_type_info():
    """ """
    with open(str(FHIR_EXAMPLE_RESOURCES / "Patient.json"), "r") as fp:
        data = fp.read()

        obj = lookup_fhir_class("Patient", FHIR_VERSION.R4).parse_raw(data)

    fpath = fhirpath.FHIRPath(obj)
    assert isinstance(fpath.get_type(), fhirpath.ClassInfo)
    # Patient has 26 elements
    assert len(fpath.get_type().element) == 26
    assert fpath.get_type().name == "Patient"
    assert fpath.get_type().baseType == "FHIR.DomainResource"
    # Test Element from Base
    assert fpath.meta.get_type().name == "Meta"


def test_fhirpath_list_type_info():
    """ """
    with open(str(FHIR_EXAMPLE_RESOURCES / "Patient.json"), "r") as fp:
        data = fp.read()
        obj = lookup_fhir_class("Patient", FHIR_VERSION.R4).parse_raw(data)
    fpath = fhirpath.FHIRPath(obj)
    assert isinstance(fpath.address.get_type(), fhirpath.ListTypeInfo)
    assert fpath.address.get_type().elementType == "FHIR.Address"
    assert isinstance(
        fhirpath.FHIRPath.__storage__[fpath.address.get_type().elementType],
        fhirpath.ClassInfo,
    )
    with pytest.raises(ValueError) as exc_info:
        fhirpath.FHIRPath(["mu", "mn"])
        assert "root fhirpath cannot be initialized" in exc_info.value.args[0]

    obj.address = None
    fpath = fhirpath.FHIRPath(obj)
    assert isinstance(fpath.address.get_type(), fhirpath.ListTypeInfo)

    obj.address = []
    fpath = fhirpath.FHIRPath(obj)
    assert isinstance(fpath.address.get_type(), fhirpath.ListTypeInfo)
    assert isinstance(fpath.extension.get_type(), fhirpath.ListTypeInfo)
    assert fpath.extension() is None


def test_fhirpath_simple_type_info():
    """ """
    with open(str(FHIR_EXAMPLE_RESOURCES / "Patient.json"), "r") as fp:
        data = fp.read()
        obj = lookup_fhir_class("Patient", FHIR_VERSION.R4).parse_raw(data)
    fpath = fhirpath.FHIRPath(obj)
    assert fpath.gender.get_type().name == "code"
    assert fpath.gender.get_type().baseType == "FHIR.Primitive"
    assert fpath.active.get_type().name == "boolean"

    assert fpath.identifier[0].type.text.get_type().name == "string"
    obj.gender = None
    obj.active = None
    fpath = fhirpath.FHIRPath(obj)
    assert fpath.gender.get_type().name == "code"
    assert fpath.active.get_type().name == "boolean"


def test_fhirpath_tuple_type_info():
    """ """
    with open(str(FHIR_EXAMPLE_RESOURCES / "Patient.json"), "r") as fp:
        data = fp.read()
        obj = lookup_fhir_class("Patient", FHIR_VERSION.R4).parse_raw(data)
    fpath = fhirpath.FHIRPath(obj)
    assert isinstance(fpath.contact[0].get_type(), fhirpath.TupleTypeInfo)
    assert len(fpath.contact[0].get_type().get_elements()) == 10
