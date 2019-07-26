#!/usr/bin/env python
# _*_ coding: utf-8 _*_
"""Tests for `fhirpath` package."""
import json
import os
import pathlib

from guillotina_elasticsearch.tests.utils import run_with_retries
from guillotina_elasticsearch.tests.utils import setup_txn_on_container

from fhirpath.search import Search
from fhirpath.search import SearchContext


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


FHIR_EXAMPLE_RESOURCES = (
    pathlib.Path(os.path.abspath(__file__)).parent / "static" / "FHIR"
)


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
