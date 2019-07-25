#!/usr/bin/env python
# _*_ coding: utf-8 _*_
"""Tests for `fhirpath` package."""
import json
import os
import pathlib

# from guillotina_elasticsearch.tests.utils import run_with_retries
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
                }
            ),
        )
        assert status == 201
