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
    assert conn.ping() is True

    # test from string path
    es_conn_factory = ES.ElasticsearchConnectionFactory(
        url, "aioelasticsearch.Elasticsearch"
    )
    conn = es_conn_factory()
    assert await conn.ping() is True

    # test connection creation from helper method
    # with default connection class elasticsearch.Elasticsearch
    conn = ES.create(url)
    assert conn.ping() is True
