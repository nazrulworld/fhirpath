# _*_ coding: utf-8 _*_
import subprocess

import pytest
from guillotina import testing
from guillotina_elasticsearch.tests.fixtures import elasticsearch

from fhirpath.engine import create_engine
from fhirpath.fhirspec import DEFAULT_SETTINGS
from fhirpath.thirdparty import attrdict
from fhirpath.utils import proxy


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def base_settings_configurator(settings):
    if "applications" not in settings:
        settings["applications"] = []

    if "guillotina_elasticsearch" not in settings["applications"]:
        settings["applications"].append("guillotina_elasticsearch")

    if "guillotina_elasticsearch.testing" not in settings["applications"]:  # noqa
        settings["applications"].append("guillotina_elasticsearch.testing")

    settings["elasticsearch"] = {
        "index_name_prefix": "guillotina-",
        "connection_settings": {
            "hosts": [
                "{}:{}".format(
                    getattr(elasticsearch, "host", "localhost"),
                    getattr(elasticsearch, "port", "9200"),
                )
            ],
            "sniffer_timeout": None,
        },
    }

    settings["load_utilities"]["catalog"] = {
        "provides": "guillotina_elasticsearch.interfaces.IElasticSearchUtility",  # noqa
        "factory": "guillotina_elasticsearch.utility.ElasticSearchUtility",
        "settings": {},
    }


testing.configure_with(base_settings_configurator)


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


@pytest.fixture
def engine():
    """ """
    engine = create_engine()
    yield proxy(engine)


def has_internet_connection():
    """ """
    try:
        res = subprocess.check_call(["ping", "-c", "1", "8.8.8.8"])
        return res == 0
    except subprocess.CalledProcessError:
        return False
