# _*_ coding: utf-8 _*_
from urllib.parse import urlencode
from fhirpath.search import Search
from fhirpath.search import SearchContext


__author__ = "Md Nazrul Islam<nazrul@zitelab.dk>"


def test_parse_query_string():
    """ """
    params = (
        ("status:not", "completed"),
        ("status", "active"),
        ("code", "http://acme.org/conditions/codes|ha125"),
        ("probability", "gt0.8"),
        ("date", "ge2010-01-01"),
        ("date", "le2011-12-31"),
        ("alue-quantity", "5.4|http://unitsofmeasure.org|mg"),
        ("definition:below", "http:http://acme.com/some-profile"),
        ("code", "http://loinc.org|1234-5&subject.name=peter"),
        ("_sort", "status,-date,category"),
        ("_count", "1"),
        ("medication.ingredient-code", "abc"),
        ("_include", "Observation:related-target"),
    )

    result = Search.parse_query_string(urlencode(params))
    assert len(result.getall("code")) == 2
    assert len(result.getall("date")) == 2
    assert len(result.getall("medication.ingredient-code")) == 1


def test_prepare_params(engine):
    """ """
    context = SearchContext(engine, "Task")
    params = (
        ("status:not", "completed"),
        ("status", "active"),
        ("code", "http://acme.org/conditions/codes|ha125"),
        ("probability", "gt0.8"),
        ("date", "ge2010-01-01"),
        ("date", "le2011-12-31"),
        ("code", "http://loinc.org|1234-5&subject.name=peter"),
        ("_sort", "status,-date,category"),
        ("_count", "1"),
    )

    fhir_search = Search(context, params=params)

    assert len(fhir_search.search_params.getall("status")) == 2
