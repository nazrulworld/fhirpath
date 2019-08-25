#!/usr/bin/env python
# _*_ coding: utf-8 _*_
"""Tests for `fhirpath` package."""
from fhirpath.search import Search
from fhirpath.search import SearchContext


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


async def test_raw_es_query_generation_from_search(engine, es_data):
    """Sample pytest test function with the pytest fixture as an argument."""
    context = SearchContext(engine, "Patient")
    params = (("gender", "male"), ("active", "true"), ("birthdate", "ge2010-01-01"))

    fhir_search = Search(context, params=params)
    result = fhir_search.build()
    engine.dialect.compile(result._query)


async def test_dialect_generated_raw_query(es_data, engine):
    """ """
    search_context = SearchContext(engine, "Organization")

    params = (
        ("active", "true"),
        ("_lastUpdated", "2010-05-28T05:35:56+00:00"),
        ("_profile", "http://hl7.org/fhir/Organization"),
        ("identifier", "urn:oid:2.16.528.1|91654"),
        ("type", "http://hl7.org/fhir/organization-type|prov"),
        ("address-postalcode", "9100 AA"),
        ("address", "Den Burg"),
    )
    search_tool = Search(context=search_context, params=params)
    result_query = search_tool.build()

    compiled = search_context.engine.dialect.compile(
        result_query._query, "organization_resource"
    )
    search_params = search_context.engine.connection.finalize_search_params(compiled)
    conn = engine.connection.raw_connection
    index_name = engine.get_index_name()

    result = conn.search(index=index_name, **search_params)
    assert len(result["hits"]["hits"]) == 1

    # test ContactPoint,HumanName
    search_context = SearchContext(engine, "Patient")

    params = (
        ("active", "true"),
        ("telecom", "2562000002"),
        ("given", "Eelector"),
        ("name", "Saint"),
        ("email", "demo1@example.com"),
        ("phone", "2562000002"),
    )
    search_tool = Search(context=search_context, params=params)
    result_query = search_tool.build()

    compiled = search_context.engine.dialect.compile(
        result_query._query, "patient_resource"
    )
    search_params = search_context.engine.connection.finalize_search_params(compiled)
    result = conn.search(index=index_name, **search_params)
    assert len(result["hits"]["hits"]) == 1

    # test Quantity, Number
    search_context = SearchContext(engine, "ChargeItem")

    params = (
        ("quantity", "1"),
        ("factor-override", "0.8"),
        ("price-override", "40|EUR"),
    )
    search_tool = Search(context=search_context, params=params)
    result_query = search_tool.build()

    compiled = search_context.engine.dialect.compile(
        result_query._query, "chargeitem_resource"
    )
    search_params = search_context.engine.connection.finalize_search_params(compiled)
    result = conn.search(index=index_name, **search_params)
    assert len(result["hits"]["hits"]) == 1
