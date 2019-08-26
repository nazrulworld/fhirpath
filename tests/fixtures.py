# _*_ coding: utf-8 _*_

import pytest
from elasticsearch.exceptions import NotFoundError

from fhirpath.connectors import create_connection
from fhirpath.fhirspec import DEFAULT_SETTINGS
from fhirpath.thirdparty import attrdict
from fhirpath.utils import proxy

from ._utils import ES_INDEX_NAME_REAL
from ._utils import TestElasticsearchEngine
from ._utils import _load_es_data
from ._utils import _setup_es_index


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


@pytest.fixture
def response():
    """Sample pytest fixture.

    See more at: http://doc.pytest.org/en/latest/fixture.html
    """
    # import requests
    # return requests.get('https://github.com/audreyr/cookiecutter-pypackage')


@pytest.fixture(scope="module")
def fhir_spec_settings():
    """ """
    settings = attrdict(DEFAULT_SETTINGS.copy())

    yield settings


@pytest.fixture(scope="session")
def es_connection(es):
    """ """
    host, port = es
    conn_str = "es://@{0}:{1}/".format(host, port)
    conn = create_connection(conn_str, "elasticsearch.Elasticsearch")
    assert conn.raw_connection.ping()
    yield conn


@pytest.fixture(scope="session")
def engine(es_connection):
    """ """
    engine = TestElasticsearchEngine(es_connection)
    yield proxy(engine)


@pytest.fixture(scope="session")
def es_data(es_connection):
    """ """
    # do create index with other settings
    _setup_es_index(es_connection)
    _load_es_data(es_connection)

    # es connection, meta data of fixture, i.e id
    yield es_connection, None
    try:
        es_connection.raw_connection.indices.delete_alias(ES_INDEX_NAME_REAL, name="*")
        es_connection.raw_connection.indices.delete(ES_INDEX_NAME_REAL)
    except NotFoundError:
        pass
