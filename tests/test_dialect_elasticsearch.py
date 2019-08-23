#!/usr/bin/env python
# _*_ coding: utf-8 _*_
"""Tests for `fhirpath` package."""
import json

from guillotina.component import query_utility
from guillotina_elasticsearch.tests.utils import run_with_retries
from guillotina_elasticsearch.tests.utils import setup_txn_on_container

from fhirpath.interfaces import ISearchContextFactory
from fhirpath.search import Search
from fhirpath.search import SearchContext

from .fixtures import FHIR_EXAMPLE_RESOURCES
from .fixtures import init_data


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


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
        search_params = search_context.engine.connection.finalize_search_params(
            compiled
        )
        result = await conn.search(index=index_name, **search_params)
        assert len(result["hits"]["hits"]) == 1
        # test ContactPoint,HumanName
        search_context = query_utility(ISearchContextFactory).get(
            resource_type="Patient"
        )
        index_name = await search_context.engine.get_index_name(container)
        conn = search_context.engine.connection.raw_connection()
        await conn.indices.refresh(index=index_name)

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
        search_params = search_context.engine.connection.finalize_search_params(
            compiled
        )
        result = await conn.search(index=index_name, **search_params)
        assert len(result["hits"]["hits"]) == 1

        # test Quantity, Number
        search_context = query_utility(ISearchContextFactory).get(
            resource_type="ChargeItem"
        )
        index_name = await search_context.engine.get_index_name(container)
        conn = search_context.engine.connection.raw_connection()
        await conn.indices.refresh(index=index_name)

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
        search_params = search_context.engine.connection.finalize_search_params(
            compiled
        )
        result = await conn.search(index=index_name, **search_params)
        assert len(result["hits"]["hits"]) == 1
"""
result = await conn.bulk(
                index=index_name, doc_type=DOC_TYPE,
                body=bulk_data)
[{'index': {'_id': '2c1|c65af61262d944b99e46ba88b7a61512',
            '_index': 'guillotina-db-guillotina_1'}},
 {'access_roles': ['guillotina.Reader',
                   'guillotina.Reviewer',
                   'guillotina.Owner',
                   'guillotina.Editor',
                   'guillotina.ContainerAdmin'],
  'access_users': ['root'],
  'creation_date': '2019-08-23T11:50:43.287601+00:00',
  'depth': 2,
  'elastic_index': 'guillotina-db-guillotina__organization-c65af61262d944b99e46ba88b7a61512',
  'id': 'f001',
  'modification_date': '2019-08-23T11:50:43.287601+00:00',
  'org_type': 'ABT',
  'organization_resource': {'active': True,
                            'address': [{'city': 'Den Burg;Jeg fik bøde på '
                                                 '5.000 kroner i et andet '
                                                 'orkester. først søge '
                                                 'permanent ophold i år 2032',
                                         'country': 'NLD',
                                         'line': ['Galapagosweg 91'],
                                         'postalCode': '9105 PZ',
                                         'use': 'work'},
                                        {'city': 'Den Burg',
                                         'country': 'NLD',
                                         'line': ['PO Box 2311'],
                                         'postalCode': '9100 AA',
                                         'use': 'work'}],
                            'contact': [{'purpose': {'coding': [{'code': 'PRESS',
                                                                 'system': 'http://hl7.org/fhir/contactentity-type'}]},
                                         'telecom': [{'system': 'phone',
                                                      'value': '022-655 '
                                                               '2334'}]},
                                        {'purpose': {'coding': [{'code': 'PATINF',
                                                                 'system': 'http://hl7.org/fhir/contactentity-type'}]},
                                         'telecom': [{'system': 'phone',
                                                      'value': '022-655 '
                                                               '2335'}]}],
                            'id': 'f001',
                            'identifier': [{'system': 'urn:oid:2.16.528.1',
                                            'use': 'official',
                                            'value': '91654'},
                                           {'system': 'urn:oid:2.16.840.1.113883.2.4.6.1',
                                            'use': 'usual',
                                            'value': '17-0112278'}],
                            'meta': {'lastUpdated': '2010-05-28T05:35:56+00:00',
                                     'profile': ['http://hl7.org/fhir/Organization',
                                                 'urn:oid:002.160'],
                                     'versionId': 'V001'},
                            'name': 'Burgers University Medical Center',
                            'resourceType': 'Organization',
                            'telecom': [{'system': 'phone',
                                         'use': 'work',
                                         'value': '022-655 2300'}],
                            'text': {'div': '<div>EMPTY</div>',
                                     'status': 'generated'},
                            'type': [{'coding': [{'code': 'V6',
                                                  'display': 'University '
                                                             'Medical '
                                                             'HospitalHBO '
                                                             'Nordic gør det '
                                                             'bedst: Her er '
                                                             'Politikens bud '
                                                             'på årets 10 '
                                                             'bedste tv-serier',
                                                  'system': 'urn:oid:2.16.840.1.113883.2.4.15.1060'},
                                                 {'code': 'prov',
                                                  'display': 'Healthcare '
                                                             'Provider',
                                                  'system': 'http://hl7.org/fhir/organization-type'}]}]},
  'parent_uuid': '2c1a8a1403a743608aafc294b6e822af',
  'path': '/f001',
  'tid': 8,
  'title': 'Burgers University Medical Center',
  'type_name': 'Organization',
  'uuid': '2c1|c65af61262d944b99e46ba88b7a61512'}]
(Pdb) pp bulk_data[0]
{'index': {'_id': '2c1|c65af61262d944b99e46ba88b7a61512',
           '_index': 'guillotina-db-guillotina_1'}}
(Pdb) pp bulk_data[1]
{'access_roles': ['guillotina.Reader',
                  'guillotina.Reviewer',
                  'guillotina.Owner',
                  'guillotina.Editor',
                  'guillotina.ContainerAdmin'],
 'access_users': ['root'],
 'creation_date': '2019-08-23T11:50:43.287601+00:00',
 'depth': 2,
 'elastic_index': 'guillotina-db-guillotina__organization-c65af61262d944b99e46ba88b7a61512',
 'id': 'f001',
 'modification_date': '2019-08-23T11:50:43.287601+00:00',
 'org_type': 'ABT',
 'organization_resource': {'active': True,
                           'address': [{'city': 'Den Burg;Jeg fik bøde på '
                                                '5.000 kroner i et andet '
                                                'orkester. først søge '
                                                'permanent ophold i år 2032',
                                        'country': 'NLD',
                                        'line': ['Galapagosweg 91'],
                                        'postalCode': '9105 PZ',
                                        'use': 'work'},
                                       {'city': 'Den Burg',
                                        'country': 'NLD',
                                        'line': ['PO Box 2311'],
                                        'postalCode': '9100 AA',
                                        'use': 'work'}],
                           'contact': [{'purpose': {'coding': [{'code': 'PRESS',
                                                                'system': 'http://hl7.org/fhir/contactentity-type'}]},
                                        'telecom': [{'system': 'phone',
                                                     'value': '022-655 2334'}]},
                                       {'purpose': {'coding': [{'code': 'PATINF',
                                                                'system': 'http://hl7.org/fhir/contactentity-type'}]},
                                        'telecom': [{'system': 'phone',
                                                     'value': '022-655 '
                                                              '2335'}]}],
                           'id': 'f001',
                           'identifier': [{'system': 'urn:oid:2.16.528.1',
                                           'use': 'official',
                                           'value': '91654'},
                                          {'system': 'urn:oid:2.16.840.1.113883.2.4.6.1',
                                           'use': 'usual',
                                           'value': '17-0112278'}],
                           'meta': {'lastUpdated': '2010-05-28T05:35:56+00:00',
                                    'profile': ['http://hl7.org/fhir/Organization',
                                                'urn:oid:002.160'],
                                    'versionId': 'V001'},
                           'name': 'Burgers University Medical Center',
                           'resourceType': 'Organization',
                           'telecom': [{'system': 'phone',
                                        'use': 'work',
                                        'value': '022-655 2300'}],
                           'text': {'div': '<div>EMPTY</div>',
                                    'status': 'generated'},
                           'type': [{'coding': [{'code': 'V6',
                                                 'display': 'University '
                                                            'Medical '
                                                            'HospitalHBO '
                                                            'Nordic gør det '
                                                            'bedst: Her er '
                                                            'Politikens bud på '
                                                            'årets 10 bedste '
                                                            'tv-serier',
                                                 'system': 'urn:oid:2.16.840.1.113883.2.4.15.1060'},
                                                {'code': 'prov',
                                                 'display': 'Healthcare '
                                                            'Provider',
                                                 'system': 'http://hl7.org/fhir/organization-type'}]}]},
 'parent_uuid': '2c1a8a1403a743608aafc294b6e822af',
 'path': '/f001',
 'tid': 8,
 'title': 'Burgers University Medical Center',
 'type_name': 'Organization',
 'uuid': '2c1|c65af61262d944b99e46ba88b7a61512'}
(Pdb) pp bulk_data[1].keys()
dict_keys(['type_name', 'tid', 'uuid', 'title', 'modification_date', 'creation_date', 'access_roles', 'id', 'access_users', 'path', 'depth', 'parent_uuid', 'elastic_index', 'organization_resource', 'org_type'])
(Pdb) pp bulk_data[1].keys()
dict_keys(['type_name', 'tid', 'uuid', 'title', 'modification_date', 'creation_date', 'access_roles', 'id', 'access_users', 'path', 'depth', 'parent_uuid', 'elastic_index', 'organization_resource', 'org_type'])
(Pdb) pp bulk_data
[{'index': {'_id': '2c1|c65af61262d944b99e46ba88b7a61512',
            '_index': 'guillotina-db-guillotina_1'}},
 {'access_roles': ['guillotina.Reader',
                   'guillotina.Reviewer',
                   'guillotina.Owner',
                   'guillotina.Editor',
                   'guillotina.ContainerAdmin'],
  'access_users': ['root'],
  'creation_date': '2019-08-23T11:50:43.287601+00:00',
  'depth': 2,
  'elastic_index': 'guillotina-db-guillotina__organization-c65af61262d944b99e46ba88b7a61512',
  'id': 'f001',
  'modification_date': '2019-08-23T11:50:43.287601+00:00',
  'org_type': 'ABT',
  'organization_resource': {'active': True,
                            'address': [{'city': 'Den Burg;Jeg fik bøde på '
                                                 '5.000 kroner i et andet '
                                                 'orkester. først søge '
                                                 'permanent ophold i år 2032',
                                         'country': 'NLD',
                                         'line': ['Galapagosweg 91'],
                                         'postalCode': '9105 PZ',
                                         'use': 'work'},
                                        {'city': 'Den Burg',
                                         'country': 'NLD',
                                         'line': ['PO Box 2311'],
                                         'postalCode': '9100 AA',
                                         'use': 'work'}],
                            'contact': [{'purpose': {'coding': [{'code': 'PRESS',
                                                                 'system': 'http://hl7.org/fhir/contactentity-type'}]},
                                         'telecom': [{'system': 'phone',
                                                      'value': '022-655 '
                                                               '2334'}]},
                                        {'purpose': {'coding': [{'code': 'PATINF',
                                                                 'system': 'http://hl7.org/fhir/contactentity-type'}]},
                                         'telecom': [{'system': 'phone',
                                                      'value': '022-655 '
                                                               '2335'}]}],
                            'id': 'f001',
                            'identifier': [{'system': 'urn:oid:2.16.528.1',
                                            'use': 'official',
                                            'value': '91654'},
                                           {'system': 'urn:oid:2.16.840.1.113883.2.4.6.1',
                                            'use': 'usual',
                                            'value': '17-0112278'}],
                            'meta': {'lastUpdated': '2010-05-28T05:35:56+00:00',
                                     'profile': ['http://hl7.org/fhir/Organization',
                                                 'urn:oid:002.160'],
                                     'versionId': 'V001'},
                            'name': 'Burgers University Medical Center',
                            'resourceType': 'Organization',
                            'telecom': [{'system': 'phone',
                                         'use': 'work',
                                         'value': '022-655 2300'}],
                            'text': {'div': '<div>EMPTY</div>',
                                     'status': 'generated'},
                            'type': [{'coding': [{'code': 'V6',
                                                  'display': 'University '
                                                             'Medical '
                                                             'HospitalHBO '
                                                             'Nordic gør det '
                                                             'bedst: Her er '
                                                             'Politikens bud '
                                                             'på årets 10 '
                                                             'bedste tv-serier',
                                                  'system': 'urn:oid:2.16.840.1.113883.2.4.15.1060'},
                                                 {'code': 'prov',
                                                  'display': 'Healthcare '
                                                             'Provider',
                                                  'system': 'http://hl7.org/fhir/organization-type'}]}]},
  'parent_uuid': '2c1a8a1403a743608aafc294b6e822af',
  'path': '/f001',
  'tid': 8,
  'title': 'Burgers University Medical Center',
  'type_name': 'Organization',
  'uuid': '2c1|c65af61262d944b99e46ba88b7a61512'}]
  """
"""
await conn.indices.create(real_index_name, settings)
(Pdb) pp settings["settings"]
{'analysis': {'analyzer': {'path_analyzer': {'tokenizer': 'path_tokenizer'}},
              'char_filter': {},
              'filter': {},
              'tokenizer': {'path_tokenizer': {'delimiter': '/',
                                               'type': 'path_hierarchy'}}}}
{'mappings': {'dynamic': False,
              'properties': {'access_roles': {'index': True,
                                              'store': True,
                                              'type': 'keyword'},
                             'access_users': {'index': True,
                                              'store': True,
                                              'type': 'keyword'},
                             'boolean_field': {'type': 'boolean'},
                             'categories': {'dynamic': False, 'type': 'nested'},
                             'categories_accessor': {'index': True,
                                                     'type': 'text'},
                             'contributors': {'index': True,
                                              'store': True,
                                              'type': 'keyword'},
                             'creation_date': {'store': True, 'type': 'date'},
                             'creators': {'index': True,
                                          'store': True,
                                          'type': 'keyword'},
                             'depth': {'type': 'integer'},
                             'elastic_index': {'index': True,
                                               'store': True,
                                               'type': 'keyword'},
                             'foobar_accessor': {'index': True, 'type': 'text'},
                             'id': {'index': True,
                                    'store': True,
                                    'type': 'keyword'},
                             'modification_date': {'store': True,
                                                   'type': 'date'},
                             'org_type': {'index': True, 'type': 'keyword'},
                             'organization_resource': {'properties': {'active': {'store': False,
                                                                                 'type': 'boolean'},
                                                                      'address': {'properties': {'city': {'index': True,
                                                                                                          'store': False,
                                                                                                          'type': 'keyword'},
                                                                                                 'country': {'index': True,
                                                                                                             'store': False,
                                                                                                             'type': 'keyword'},
                                                                                                 'postalCode': {'index': True,
                                                                                                                'store': False,
                                                                                                                'type': 'keyword'},
                                                                                                 'state': {'index': True,
                                                                                                           'store': False,
                                                                                                           'type': 'keyword'},
                                                                                                 'use': {'index': True,
                                                                                                         'store': False,
                                                                                                         'type': 'keyword'}},
                                                                                  'type': 'nested'},
                                                                      'alias': {'index': True,
                                                                                'store': False,
                                                                                'type': 'keyword'},
                                                                      'endpoint': {'properties': {'reference': {'index': True,
                                                                                                                'store': False,
                                                                                                                'type': 'keyword'}},
                                                                                   'type': 'nested'},
                                                                      'id': {'index': True,
                                                                             'store': False,
                                                                             'type': 'keyword'},
                                                                      'identifier': {'properties': {'system': {'index': True,
                                                                                                               'store': False,
                                                                                                               'type': 'keyword'},
                                                                                                    'type': {'properties': {'text': {'analyzer': 'standard',
                                                                                                                                     'index': True,
                                                                                                                                     'store': False,
                                                                                                                                     'type': 'text'}}},
                                                                                                    'use': {'index': True,
                                                                                                            'store': False,
                                                                                                            'type': 'keyword'},
                                                                                                    'value': {'index': True,
                                                                                                              'store': False,
                                                                                                              'type': 'keyword'}},
                                                                                     'type': 'nested'},
                                                                      'meta': {'properties': {'lastUpdated': {'format': 'date_time_no_millis||date_optional_time',
                                                                                                              'store': False,
                                                                                                              'type': 'date'},
                                                                                              'profile': {'index': True,
                                                                                                          'store': False,
                                                                                                          'type': 'keyword'},
                                                                                              'versionId': {'index': True,
                                                                                                            'store': False,
                                                                                                            'type': 'keyword'}}},
                                                                      'name': {'index': True,
                                                                               'store': False,
                                                                               'type': 'keyword'},
                                                                      'partOf': {'properties': {'reference': {'index': True,
                                                                                                              'store': False,
                                                                                                              'type': 'keyword'}}},
                                                                      'resourceType': {'index': True,
                                                                                       'store': False,
                                                                                       'type': 'keyword'},
                                                                      'type': {'properties': {'coding': {'properties': {'code': {'index': True,
                                                                                                                                 'store': False,
                                                                                                                                 'type': 'keyword'},
                                                                                                                        'display': {'index': True,
                                                                                                                                    'store': False,
                                                                                                                                    'type': 'keyword'},
                                                                                                                        'system': {'index': True,
                                                                                                                                   'store': False,
                                                                                                                                   'type': 'keyword'}},
                                                                                                         'type': 'nested'},
                                                                                              'text': {'analyzer': 'standard',
                                                                                                       'index': True,
                                                                                                       'store': False,
                                                                                                       'type': 'text'}},
                                                                               'type': 'nested'}}},
                             'p_type': {'index': True, 'type': 'keyword'},
                             'parent_uuid': {'index': True,
                                             'store': True,
                                             'type': 'keyword'},
                             'path': {'analyzer': 'path_analyzer',
                                      'store': True,
                                      'type': 'text'},
                             'tags': {'index': True,
                                      'store': True,
                                      'type': 'keyword'},
                             'tid': {'index': True,
                                     'store': True,
                                     'type': 'keyword'},
                             'title': {'index': True,
                                       'store': True,
                                       'type': 'text'},
                             'type_name': {'index': True,
                                           'store': True,
                                           'type': 'keyword'},
                             'uuid': {'index': True,
                                      'store': True,
                                      'type': 'keyword'}}},
 'settings': {'analysis': {'analyzer': {'path_analyzer': {'tokenizer': 'path_tokenizer'}},
                           'char_filter': {},
                           'filter': {},
                           'tokenizer': {'path_tokenizer': {'delimiter': '/',
                                                            'type': 'path_hierarchy'}}}}}

"""
