# _*_ coding: utf-8 _*_
import asyncio
import copy
import json
import uuid

import pytest
from elasticsearch.exceptions import NotFoundError
from fhir.resources.organization import Organization as fhir_org
from fhir.resources.task import Task as fhir_task
from guillotina import configure
from guillotina import testing
from guillotina.api.service import Service
from guillotina.component import get_utility
from guillotina.content import Folder
from guillotina.content import Item
from guillotina.directives import index_field
from guillotina.interfaces import ICatalogUtility
from guillotina.interfaces import IContainer
from guillotina.schema import TextLine
from guillotina_elasticsearch.directives import index
from guillotina_elasticsearch.interfaces import IContentIndex
from guillotina_elasticsearch.tests.fixtures import elasticsearch
from zope.interface import implementer

from fhirpath.connectors import create_connection
from fhirpath.engine import create_engine
from fhirpath.enums import FHIR_VERSION
from fhirpath.fhirspec import DEFAULT_SETTINGS
from fhirpath.providers.guillotina_app.field import FhirField
from fhirpath.providers.guillotina_app.interfaces import IFhirContent
from fhirpath.providers.guillotina_app.interfaces import IFhirResource
from fhirpath.thirdparty import attrdict
from fhirpath.utils import proxy

from ._utils import ES_INDEX_NAME_REAL
from ._utils import FHIR_EXAMPLE_RESOURCES
from ._utils import _load_es_data
from ._utils import _setup_es_index
from ._utils import fhir_resource_mapping


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


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


@pytest.fixture(scope="session")
def es_connection(es):
    """ """
    host, port = es
    conn_str = "es://@{0}:{1}/".format(host, port)
    conn = create_connection(conn_str, "elasticsearch.Elasticsearch")
    assert conn.ping()
    yield conn


@pytest.fixture(scope="session")
def engine(es_connection):
    """ """
    engine = create_engine(es_connection)
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
        es_connection.indices.delete_alias(ES_INDEX_NAME_REAL, name="*")
        es_connection.indices.delete(ES_INDEX_NAME_REAL)
    except NotFoundError:
        pass


class IOrganization(IFhirContent, IContentIndex):

    index_field(
        "organization_resource",
        type="object",
        field_mapping=fhir_resource_mapping("Organization"),
        fhirpath_enabled=True,
        resource_type="Organization",
        fhir_version=FHIR_VERSION.DEFAULT,
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


class IPatient(IFhirContent, IContentIndex):

    index_field(
        "patient_resource",
        type="object",
        field_mapping=fhir_resource_mapping("Patient"),
        fhirpath_enabled=True,
        resource_type="Patient",
        fhir_version=FHIR_VERSION.DEFAULT,
    )
    index_field("p_type", type="keyword")
    p_type = TextLine(title="Patient Type", required=False)
    patient_resource = FhirField(
        title="Patient Resource", resource_type="Patient", fhir_version="R4"
    )


@configure.contenttype(type_name="Patient", schema=IPatient)
class Patient(Folder):
    """ """

    index(schemas=[IPatient], settings={})
    resource_type = "Patient"


class IChargeItem(IFhirContent, IContentIndex):

    index_field(
        "chargeitem_resource",
        type="object",
        field_mapping=fhir_resource_mapping("ChargeItem"),
        fhirpath_enabled=True,
        resource_type="ChargeItem",
        fhir_version=FHIR_VERSION.DEFAULT,
    )

    chargeitem_resource = FhirField(
        title="Charge Item Resource", resource_type="ChargeItem", fhir_version="R4"
    )


@configure.contenttype(type_name="ChargeItem", schema=IChargeItem)
class ChargeItem(Item):
    """ """

    index(schemas=[IChargeItem], settings={})
    resource_type = "ChargeItem"


class IMedicationRequest(IFhirContent, IContentIndex):

    index_field(
        "medicationrequest_resource",
        type="object",
        field_mapping=fhir_resource_mapping("MedicationRequest"),
        fhirpath_enabled=True,
        resource_type="MedicationRequest",
        fhir_version=FHIR_VERSION.DEFAULT,
    )

    medicationrequest_resource = FhirField(
        title="Medication Request Resource",
        resource_type="MedicationRequest",
        fhir_version="R4",
    )


@configure.contenttype(type_name="MedicationRequest", schema=IMedicationRequest)
class MedicationRequest(Item):
    """ """

    index(schemas=[IMedicationRequest], settings={})
    resource_type = "MedicationRequest"


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


async def init_data(requester):
    """ """
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

    with open(str(FHIR_EXAMPLE_RESOURCES / "Patient.json"), "r") as fp:
        data = json.load(fp)

    resp, status = await requester(
        "POST",
        "/db/guillotina/",
        data=json.dumps(
            {
                "@type": "Patient",
                "title": data["name"][0]["text"],
                "id": data["id"],
                "patient_resource": data,
            }
        ),
    )
    assert status == 201

    with open(str(FHIR_EXAMPLE_RESOURCES / "ChargeItem.json"), "r") as fp:
        data = json.load(fp)

    resp, status = await requester(
        "POST",
        "/db/guillotina/",
        data=json.dumps(
            {
                "@type": "ChargeItem",
                "title": "Chargeble Bill",
                "id": data["id"],
                "chargeitem_resource": data,
            }
        ),
    )
    assert status == 201

    with open(str(FHIR_EXAMPLE_RESOURCES / "MedicationRequest.json"), "r") as fp:
        data = json.load(fp)

    resp, status = await requester(
        "POST",
        "/db/guillotina/",
        data=json.dumps(
            {
                "@type": "MedicationRequest",
                "title": "Prescription",
                "id": data["id"],
                "medicationrequest_resource": data,
            }
        ),
    )
    assert status == 201


async def load_organizations_data(requester, count=1):
    """ """
    with open(str(FHIR_EXAMPLE_RESOURCES / "Organization.json"), "r") as fp:
        data = json.load(fp)
    added = 0

    while count > added:
        data_ = copy.deepcopy(data)
        data_["id"] = str(uuid.uuid4())
        resp, status = await requester(
            "POST",
            "/db/guillotina/",
            data=json.dumps(
                {
                    "@type": "Organization",
                    "title": "{0}-{1}".format(data_["name"], data_["id"]),
                    "id": data_["id"],
                    "organization_resource": data_,
                    "org_type": "ABT",
                }
            ),
        )
        assert status == 201
        added += 1
        if added % 100 == 0:
            await asyncio.sleep(1)
