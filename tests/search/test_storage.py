#!/usr/bin/env python
# -*- coding: utf-8 -*-
from fhirpath.search import storage
from fhirpath.enums import FHIR_VERSION


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


def test_fhir_releases_exists():
    """ """
    for rel in FHIR_VERSION:
        if rel.name == "DEFAULT":
            continue
        assert rel.name in storage.FHIR_RESOURCE_CLASS_STORAGE
        assert rel.name in storage.FHIR_RESOURCE_SPEC_STORAGE
        assert rel.name in storage.PATH_INFO_STORAGE
        assert rel.name in storage.SEARCH_PARAMETERS_STORAGE
