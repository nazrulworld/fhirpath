# _*_ coding: utf-8 _*_
from fhirpath.core.element import Element

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

from fhirpath.enums import FHIR_VERSION
from fhirpath.utils import lookup_fhir_class
from tests._utils import FHIR_EXAMPLE_RESOURCES


def test_element_init():
    """ """
    with open(str(FHIR_EXAMPLE_RESOURCES / "Patient.json"), "r") as fp:
        data = fp.read()
        obj = lookup_fhir_class("Patient", FHIR_VERSION.R4B).parse_raw(data)
        el = Element(obj)
        assert len(el.query("name")) == 2
        res = el.query("name[0]")
        assert len(res) == 1
        assert not isinstance(res[0].element_value(), list)


def test_element_with_where_filter():
    """ """
    with open(str(FHIR_EXAMPLE_RESOURCES / "Patient.json"), "r") as fp:
        data = fp.read()
        obj = lookup_fhir_class("Patient", FHIR_VERSION.R4B).parse_raw(data)

    el = Element(obj)
    res = el.query("name.where(use = 'official')")
    assert len(res) == 1

    res = el.query("name.where(use = 'usual' or family = 'Herbar')")
    assert len(res) == 2

    res = el.query("name.where(use = 'usual' and family = 'Herbar')")
    assert len(res) == 0

    res = el.query("name.where(use = 'usual' and given[0] = 'Elector')")
    assert len(res) == 1
    assert res[0].element_value().given[0] == "Elector"

    res = el.query("name.where(use = 'official' and given[0] = 'Elector')")
    assert len(res) == 0

    res = el.query("name.where(use = 'official' and given[0] != 'Elector')")
    assert res[0].element_value().given[0] != "Elector"
