# _*_ coding: utf-8 _*_
from elasticsearch import Elasticsearch

from fhirpath.connectors import make_url
from fhirpath.connectors.factory import es as ES


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


async def test_elasticsearch_conn_creation(es):
    """ """
    host, port = es
    conn_str = "es://@{0}:{1}/".format(host, port)
    url = make_url(conn_str)

    es_conn_factory = ES.ElasticsearchConnectionFactory(url, Elasticsearch)
    conn = es_conn_factory()
    assert conn.raw_connection.ping() is True

    # test from string path
    es_conn_factory = ES.ElasticsearchConnectionFactory(
        url, "elasticsearch.AsyncElasticsearch"
    )
    conn = es_conn_factory()
    assert await conn.raw_connection.ping() is True

    # test connection creation from helper method
    # with default connection class elasticsearch.Elasticsearch
    conn = ES.create(url)
    assert conn.raw_connection.ping() is True


def test_es_factory_complex_url_params():
    """ """
    url = (
        "es://user:secret@127.0.0.1:9200/?"
        "use_ssl=1&sniff_on_start=True&sniffer_timeout=3&"
        "max_retries=3&retry_on_status=310,330,334&url_prefix=es"
        "&serializer=fhirpath.connectors.factory.es.ElasticsearchJSONSerializer"
    )
    factory = ES.ElasticsearchConnectionFactory(
        make_url(url), "elasticsearch.AsyncElasticsearch"
    )
    params = factory.prepare_params()
    assert params["hosts"][0]["use_ssl"] is True
    assert params["retry_on_status"] == (310, 330, 334)
    assert isinstance(params["serializer"], ES.ElasticsearchJSONSerializer)
