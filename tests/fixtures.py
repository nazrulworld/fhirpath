# _*_ coding: utf-8 _*_

import os

import pytest
from pytest_docker_fixtures import IS_TRAVIS

from fhirpath.connectors import create_connection
from fhirpath.fhirspec import DEFAULT_SETTINGS
from fhirpath.thirdparty import attrdict
from fhirpath.utils import proxy

from ._utils import TestElasticsearchEngine
from ._utils import _cleanup_es
from ._utils import _init_fhirbase_structure
from ._utils import _load_es_data
from ._utils import _setup_es_index
from ._utils import pg_image


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
def fhirbase_pg():
    if os.environ.get("POSTGRESQL"):
        yield os.environ["POSTGRESQL"].split(":")
    else:
        if IS_TRAVIS:
            host = "localhost"
            port = 6379
        else:
            host, port = pg_image.run()

        yield host, port  # provide the fixture value

        if not IS_TRAVIS:
            pg_image.stop()


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


@pytest.fixture
def es_data(es_connection):
    """ """
    # do create index with other settings
    _setup_es_index(es_connection)
    _load_es_data(es_connection)

    # es connection, meta data of fixture, i.e id
    yield es_connection, None
    # clean up
    _cleanup_es(es_connection.raw_connection)


@pytest.fixture(scope="session")
def init_fhirbase_pg(fhirbase_pg):
    """ """
    host, port = fhirbase_pg
    conn_str = "pg://postgres:@{0}:{1}/fhir_db".format(host, port)
    connection = create_connection(conn_str)
    _init_fhirbase_structure(connection)
    yield connection
