# _*_ coding: utf-8 _*_
import io
import json
import os
import pathlib
import subprocess

import pytest
from fhir.resources.organization import Organization as fhir_org
from fhir.resources.task import Task as fhir_task
from guillotina import configure
from guillotina import testing
from guillotina.api.service import Service
from guillotina.component import get_utility
from guillotina.content import Folder
from guillotina.schema import TextLine
from guillotina.directives import index_field
from guillotina.interfaces import ICatalogUtility
from guillotina.interfaces import IContainer
from guillotina_elasticsearch.directives import index
from guillotina_elasticsearch.interfaces import IContentIndex
from guillotina_elasticsearch.tests.fixtures import elasticsearch
from zope.interface import implementer

from fhirpath.engine import create_engine
from fhirpath.providers.guillotina_app.field import FhirField
from fhirpath.providers.guillotina_app.helpers import FHIR_ES_MAPPINGS_CACHE
from fhirpath.providers.guillotina_app.interfaces import IFhirContent
from fhirpath.providers.guillotina_app.interfaces import IFhirResource
from fhirpath.fhirspec import DEFAULT_SETTINGS
from fhirpath.thirdparty import attrdict
from fhirpath.utils import proxy
from fhirpath.enums import FHIR_VERSION


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

ES_JSON_MAPPING_DIR = (
    pathlib.Path(os.path.dirname(os.path.abspath(__file__))).parent
    / "static"
    / "fhir"
    / "elasticsearch"
    / "mappings"
    / "R4"
)


def base_settings_configurator(settings):
    if "applications" not in settings:
        settings["applications"] = []

    if "guillotina_elasticsearch" not in settings["applications"]:
        settings["applications"].append("guillotina_elasticsearch")

    if "guillotina_elasticsearch.testing" not in settings["applications"]:  # noqa
        settings["applications"].append("guillotina_elasticsearch.testing")

    # Add App
    settings["applications"].append("fhirpath.providers.guillotina_app")
    settings["applications"].append("tests.fixtures")

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


def fhir_resource_mapping(resource_type: str, cache: bool = True):

    """"""
    if resource_type in FHIR_ES_MAPPINGS_CACHE and cache:

        return FHIR_ES_MAPPINGS_CACHE[resource_type]

    filename = f"{resource_type}.mapping.json"

    with io.open(str(ES_JSON_MAPPING_DIR / filename), "r", encoding="utf8") as fp:

        mapping_dict = json.load(fp)
        FHIR_ES_MAPPINGS_CACHE[resource_type] = mapping_dict["mapping"]

    return FHIR_ES_MAPPINGS_CACHE[resource_type]


class IOrganization(IFhirContent, IContentIndex):

    index_field(
        "organization_resource",
        type="object",
        field_mapping=fhir_resource_mapping("Organization"),
        fhirpath_enabled=True,
        resource_type="Organization",
        fhir_version=FHIR_VERSION.DEFAULT
    )
    index_field("org_type", type="keyword")
    org_type = TextLine(title="Organization Type", required=False)
    organization_resource = FhirField(
        title="Organization Resource", resource_type="Organization", fhir_version="R4"
    )


@configure.contenttype(type_name="Organization", schema=IOrganization)
class Organization(Folder):
    """ """

    index(schemas=[IOrganization], settings={})
    resource_type = "Organization"


@configure.service(
    context=IContainer,
    method="GET",
    permission="guillotina.AccessContent",
    name="@fhir/{resource_type}",
    summary="FHIR search result",
    responses={
        "200": {
            "description": "Result results on FHIR Bundle",
            "schema": {"properties": {}},
        }
    },
)
class FhirServiceSearch(Service):
    async def prepare(self):
        pass

    async def __call__(self):
        catalog = get_utility(ICatalogUtility)
        await catalog.stats(self.context)
        # import pytest;pytest.set_trace()


@implementer(IFhirResource)
class MyOrganizationResource(fhir_org):
    """ """


@implementer(IFhirResource)
class MyTaskResource(fhir_task):
    """ """


class NoneInterfaceClass(object):
    """docstring for ClassName"""


class IWrongInterface(IFhirResource):
    """ """

    def meta():
        """ """
