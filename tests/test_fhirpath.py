#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

import pytest

from fhirpath.enums import FHIR_VERSION
from fhirpath.fhirpath import FHIRPath
from fhirpath.fhirspec import lookup_fhir_resource_spec
from fhirpath.utils import lookup_fhir_class

from ._utils import FHIR_EXAMPLE_RESOURCES


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


def test_fhirpath_access_member():
    """ """
    with open(str(FHIR_EXAMPLE_RESOURCES / "Patient.json"), "r") as fp:
        data = fp.read()
        obj = lookup_fhir_class("Patient", FHIR_VERSION.R4)(json.loads(data))
    fpath = FHIRPath(obj)
    assert fpath.name.count() == 1
