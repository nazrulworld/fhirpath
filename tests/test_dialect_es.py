#!/usr/bin/env python
# _*_ coding: utf-8 _*_
"""Tests for `fhirpath` package."""
from fhirpath.search import Search
from fhirpath.search import SearchContext


def test_raw_es_query_generation_from_search(engine):
    """Sample pytest test function with the pytest fixture as an argument."""
    context = SearchContext(engine, "Patient")
    params = (
        ("gender", "male"),
        ("active", "true"),
        ("birthdate", "ge2010-01-01"),
    )

    fhir_search = Search(context, params=params)
    result = fhir_search.build()
    engine.dialect.compile(result._query)
