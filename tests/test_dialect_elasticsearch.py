#!/usr/bin/env python
# _*_ coding: utf-8 _*_
"""Tests for `fhirpath` package."""
import json
import os
import pathlib

from guillotina.component import query_utility
from guillotina_elasticsearch.tests.utils import run_with_retries
from guillotina_elasticsearch.tests.utils import setup_txn_on_container

from fhirpath.interfaces import ISearchContextFactory
from fhirpath.providers.guillotina_app.interfaces import IFhirSearch
from fhirpath.search import Search
from fhirpath.search import SearchContext


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


FHIR_EXAMPLE_RESOURCES = (
    pathlib.Path(os.path.abspath(__file__)).parent / "static" / "FHIR"
)


async def init_data(requester):
    """ """
    with open(str(FHIR_EXAMPLE_RESOURCES / "Organization.json"), "r") as fp:
        data = json.load(fp)

    resp, status = await requester(
        "POST",
        "/db/guillotina/",
        data=json.dumps(
            {
                "@type": "Organization",
                "title": data["name"],
                "id": data["id"],
                "organization_resource": data,
                "org_type": "ABT",
            }
        ),
    )
    assert status == 201


async def test_raw_es_query_generation_from_search(engine, es_requester):
    """Sample pytest test function with the pytest fixture as an argument."""
    context = SearchContext(engine, "Patient")
    params = (("gender", "male"), ("active", "true"), ("birthdate", "ge2010-01-01"))

    fhir_search = Search(context, params=params)
    result = fhir_search.build()
    engine.dialect.compile(result._query)


async def test_basic_search(es_requester):
    """Testing basic query from guillotina_elasticsearch """
    async with es_requester as requester:
        container, request, txn, tm = await setup_txn_on_container(requester)  # noqa

        with open(str(FHIR_EXAMPLE_RESOURCES / "Organization.json"), "r") as fp:
            data = json.load(fp)

        resp, status = await requester(
            "POST",
            "/db/guillotina/",
            data=json.dumps(
                {
                    "@type": "Organization",
                    "title": data["name"],
                    "id": data["id"],
                    "organization_resource": data,
                    "org_type": "ABT",
                }
            ),
        )
        assert status == 201
        # we making sure that normal ES based query is working!

        async def _test():
            term_query = {"filter": [{"term": {"org_type": "ABT"}}]}
            resp, status = await requester(
                "POST",
                "/db/guillotina/@search",
                data=json.dumps({"query": {"bool": {"filter": {"bool": term_query}}}}),
            )
            assert resp["items_count"] == 1
            assert resp["member"][0]["path"] == "/" + data["id"]

        await run_with_retries(_test, requester)
        # test with normal search query

        async def _test():
            term_query = {"filter": [{"term": {"organization_resource.active": True}}]}
            resp, status = await requester(
                "POST",
                "/db/guillotina/@search",
                data=json.dumps({"query": {"bool": {"filter": {"bool": term_query}}}}),
            )
            assert resp["items_count"] == 1
            assert resp["member"][0]["path"] == "/" + data["id"]

        await run_with_retries(_test, requester)


async def test_dialect_generated_raw_query(es_requester):
    """ """
    async with es_requester as requester:
        container, request, txn, tm = await setup_txn_on_container(requester)  # noqa
        # init primary data
        await init_data(requester)
        search_context = query_utility(ISearchContextFactory).get(
            resource_type="Organization"
        )
        index_name = await search_context.engine.get_index_name(container)

        conn = search_context.engine.connection.raw_connection()
        await conn.indices.refresh(index=index_name)

        search_tool = query_utility(IFhirSearch)
        params = (
            ("active", "true"),
            ("_lastUpdated", "2010-05-28T05:35:56+00:00"),
            ("_profile", "http://hl7.org/fhir/Organization"),
            ("identifier", "urn:oid:2.16.528.1|91654"),
            ("type", "http://hl7.org/fhir/organization-type|prov")
        )

        result_query = search_tool(params, context=search_context)

        compiled = search_context.engine.dialect.compile(
            result_query._query, "organization_resource"
        )
        search_params = search_context.engine.connection.finalize_search_params(
            compiled
        )
        result = await conn.search(index=index_name, **search_params)
        assert len(result["hits"]["hits"]) == 1
        with open("output.json", "w") as fp:
            fp.write(json.dumps(result, indent=2))
