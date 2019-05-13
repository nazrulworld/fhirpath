# _*_ coding: utf-8 _*_
import pytest

from fhirpath.fhirspec import FHIRSpec
from fhirpath.fhirspec import FhirSpecFactory
from fhirpath.thirdparty import attrdict


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def test_fhirspec_creation_using_factory(fhir_spec_settings):
    """ """
    # settings = attrdict() + fhir_spec_settings.copy()
    # directory = "${fhirpath}/fhirpath/fhirspec/R4"

    # spec = FHIRSpec(directory, settings)
    spec = FhirSpecFactory.from_release("R4", fhir_spec_settings)
    pytest.set_trace()
