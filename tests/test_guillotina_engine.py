# _*_ coding: utf-8 _*_
from fhirpath.enums import FHIR_VERSION
from fhirpath.providers.guillotina_app.engine import EsEngine


__author__ = "Md Nazrul Islam<nazrul@zitelab.dk>"


def test_engine_calculate_field_index_name(dummy_guillotina):
    """ """
    engine = EsEngine(FHIR_VERSION.DEFAULT, lambda x: "Y", lambda x: "Y")
    name = engine.calculate_field_index_name("Organization")

    assert name == "organization_resource"

    name = engine.calculate_field_index_name("NonRegisteredContentType")
    assert name is None
