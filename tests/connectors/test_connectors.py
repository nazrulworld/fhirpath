# _*_ coding: utf-8 _*_
from elasticsearch import Elasticsearch

from fhirpath.connectors import create_connection


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


def test_es_connection_creation(es):
    """ """
    host, port = es
    conn_str = "es://@{0}:{1}/".format(host, port)
    conn = create_connection(conn_str, Elasticsearch)

    assert conn.ping() is True
