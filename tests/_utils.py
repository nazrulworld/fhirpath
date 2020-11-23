# _*_ coding: utf-8 _*_
import io
import json
import os
import pathlib
import subprocess
import time
import uuid

import elasticsearch
import yarl
from pytest_docker_fixtures.containers._base import BaseImage

from fhirpath.engine import dialect_factory
from fhirpath.engine.es import ElasticsearchEngine
from fhirpath.engine.es import AsyncElasticsearchEngine
from fhirpath.enums import FHIR_VERSION
from fhirpath.storage import MemoryStorage


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

FHIR_ES_MAPPINGS_CACHE = MemoryStorage()
ES_JSON_MAPPING_DIR = (
    pathlib.Path(os.path.dirname(os.path.abspath(__file__))).parent
    / "static"
    / "fhir"
    / "elasticsearch"
    / "mappings"
    / "R4"
)
FHIR_EXAMPLE_RESOURCES = (
    pathlib.Path(os.path.abspath(__file__)).parent / "_static" / "FHIR"
)
FHIRBASE_STRUCTURE_DIR = (
    pathlib.Path(os.path.dirname(os.path.abspath(__file__))).parent
    / "static"
    / "fhirbase"
)
DOC_TYPE = "_doc"

ES_INDEX_NAME = "fhirpath_elasticsearch_index"
ES_INDEX_NAME_REAL = "fhirpath_elasticsearch_index_1"
IS_TRAVIS = os.environ.get("TRAVIS", "") != ""


class TestElasticsearchEngine(ElasticsearchEngine):
    """ """

    def __init__(self, connection):
        """ """
        ElasticsearchEngine.__init__(
            self, FHIR_VERSION.R4, lambda x: connection, dialect_factory
        )

    def get_index_name(self):
        """ """
        return ES_INDEX_NAME_REAL

    def calculate_field_index_name(self, resource_type):
        """ """
        return "{0}_resource".format(resource_type.lower())

    def get_mapping(self, resource_type):
        """ """
        mapping = fhir_resource_mapping(resource_type)
        return mapping

    def current_url(self):
        """ """
        return yarl.URL("http://nohost/@fhir")

    def extract_hits(self, selects, hits, container):
        """ """
        return ElasticsearchEngine.extract_hits(
            self, selects, hits, container, DOC_TYPE
        )


class TestAsyncElasticsearchEngine(AsyncElasticsearchEngine):
    """ """

    def __init__(self, connection):
        """ """
        ElasticsearchEngine.__init__(
            self, FHIR_VERSION.R4, lambda x: connection, dialect_factory
        )

    def get_index_name(self):
        """ """
        return ES_INDEX_NAME_REAL

    def calculate_field_index_name(self, resource_type):
        """ """
        return "{0}_resource".format(resource_type.lower())

    def get_mapping(self, resource_type):
        """ """
        mapping = fhir_resource_mapping(resource_type)
        return mapping

    def current_url(self):
        """ """
        return yarl.URL("http://nohost/@fhir")

    def extract_hits(self, selects, hits, container):
        """ """
        return ElasticsearchEngine.extract_hits(
            self, selects, hits, container, DOC_TYPE
        )


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


def load_organizations_data(es_conn, count=1):
    """ """
    added = 0
    conn = es_conn.raw_connection

    while count > added:
        organization_data = _make_index_item("Organization")
        bulk_data = [
            {"index": {"_id": organization_data["uuid"], "_index": ES_INDEX_NAME_REAL}},
            organization_data,
        ]
        res = conn.bulk(index=ES_INDEX_NAME_REAL, doc_type=DOC_TYPE, body=bulk_data)
        assert res["errors"] is False
        added += 1
        if added % 100 == 0:
            time.sleep(1)

    conn.indices.refresh(index=ES_INDEX_NAME_REAL)


def _setup_es_index(es_conn):
    """ """
    conn = es_conn.raw_connection

    body = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "fhir_reference_analyzer": {
                        "tokenizer": "keyword",
                        "filter": ["fhir_reference_filter"],
                    },
                },
                "filter": {
                    "fhir_reference_filter": {
                        "type": "pattern_capture",
                        "preserve_original": True,
                        "patterns": [r"(?:\w+\/)?(https?\:\/\/.*|[a-zA-Z0-9_-]+)"],
                    },
                },
                "char_filter": {},
                "tokenizer": {},
            },
            "index": {
                "mapping": {
                    "total_fields": {"limit": 5000},
                    "depth": {"limit": 50},
                    "nested_fields": {"limit": 500},
                }
            },
        },
        "mappings": {
            "dynamic": False,
            "properties": {
                "access_roles": {"index": True, "store": True, "type": "keyword"},
                "access_users": {"index": True, "store": True, "type": "keyword"},
                "depth": {"type": "integer"},
                "elastic_index": {"index": True, "store": True, "type": "keyword"},
                "id": {"index": True, "store": True, "type": "keyword"},
                "uuid": {"index": True, "store": True, "type": "keyword"},
            },
        },
    }

    org_mapping = fhir_resource_mapping("Organization")
    patient_mapping = fhir_resource_mapping("Patient")
    practitioner_mapping = fhir_resource_mapping("Practitioner")
    medicationrequest_mapping = fhir_resource_mapping("MedicationRequest")
    chargeitem_mapping = fhir_resource_mapping("ChargeItem")
    observation_mapping = fhir_resource_mapping("Observation")
    task_mapping = fhir_resource_mapping("Task")
    encounter_mapping = fhir_resource_mapping("Encounter")
    careplan_mapping = fhir_resource_mapping("CarePlan")
    documentreference_mapping = fhir_resource_mapping("DocumentReference")

    body["mappings"]["properties"]["organization_resource"] = org_mapping
    body["mappings"]["properties"]["patient_resource"] = patient_mapping
    body["mappings"]["properties"]["practitioner_resource"] = practitioner_mapping
    body["mappings"]["properties"][
        "medicationrequest_resource"
    ] = medicationrequest_mapping
    body["mappings"]["properties"]["chargeitem_resource"] = chargeitem_mapping
    body["mappings"]["properties"]["observation_resource"] = observation_mapping
    body["mappings"]["properties"]["task_resource"] = task_mapping
    body["mappings"]["properties"]["encounter_resource"] = encounter_mapping
    body["mappings"]["properties"]["careplan_resource"] = careplan_mapping
    body["mappings"]["properties"]["documentreference_resource"] = documentreference_mapping

    conn.indices.create(ES_INDEX_NAME_REAL, body=body)
    conn.indices.refresh(index=ES_INDEX_NAME_REAL)


def _make_index_item(resource_type):
    """ """

    id_prefix = "2c1|"
    uuid_ = uuid.uuid4().hex

    tpl = {
        "access_roles": [
            "guillotina.Reader",
            "guillotina.Reviewer",
            "guillotina.Owner",
            "guillotina.Editor",
            "guillotina.ContainerAdmin",
        ],
        "access_users": ["root"],
        "depth": 2,
        "elastic_index": "{0}__{1}-{2}".format(
            ES_INDEX_NAME, resource_type.lower(), uuid_
        ),
        "id": None,
        "uuid": id_prefix + uuid_,
    }

    with open(str(FHIR_EXAMPLE_RESOURCES / (resource_type + ".json")), "r") as fp:
        data = json.load(fp)

    tpl["id"] = data["id"]
    tpl[resource_type.lower() + "_resource"] = data

    return tpl


def _load_es_data(es_conn):
    """ """
    conn = es_conn.raw_connection
    organization_data = _make_index_item("Organization")
    bulk_data = [
        {"index": {"_id": organization_data["uuid"], "_index": ES_INDEX_NAME_REAL}},
        organization_data,
    ]
    res = conn.bulk(index=ES_INDEX_NAME_REAL, doc_type=DOC_TYPE, body=bulk_data)
    assert res["errors"] is False

    patient_data = _make_index_item("Patient")
    bulk_data = [
        {"index": {"_id": patient_data["uuid"], "_index": ES_INDEX_NAME_REAL}},
        patient_data,
    ]
    res = conn.bulk(index=ES_INDEX_NAME_REAL, doc_type=DOC_TYPE, body=bulk_data)
    assert res["errors"] is False

    practitioner_data = _make_index_item("Practitioner")
    bulk_data = [
        {"index": {"_id": practitioner_data["uuid"], "_index": ES_INDEX_NAME_REAL}},
        practitioner_data,
    ]
    res = conn.bulk(index=ES_INDEX_NAME_REAL, doc_type=DOC_TYPE, body=bulk_data)
    assert res["errors"] is False

    medicationrequest_data = _make_index_item("MedicationRequest")
    bulk_data = [
        {
            "index": {
                "_id": medicationrequest_data["uuid"],
                "_index": ES_INDEX_NAME_REAL,
            }
        },
        medicationrequest_data,
    ]
    res = conn.bulk(index=ES_INDEX_NAME_REAL, doc_type=DOC_TYPE, body=bulk_data)
    assert res["errors"] is False

    chargeitem_data = _make_index_item("ChargeItem")
    bulk_data = [
        {"index": {"_id": chargeitem_data["uuid"], "_index": ES_INDEX_NAME_REAL}},
        chargeitem_data,
    ]
    res = conn.bulk(index=ES_INDEX_NAME_REAL, doc_type=DOC_TYPE, body=bulk_data)
    assert res["errors"] is False

    observation_data = _make_index_item("Observation")
    bulk_data = [
        {"index": {"_id": observation_data["uuid"], "_index": ES_INDEX_NAME_REAL}},
        observation_data,
    ]
    res = conn.bulk(index=ES_INDEX_NAME_REAL, doc_type=DOC_TYPE, body=bulk_data)
    assert res["errors"] is False

    task_data = _make_index_item("Task")
    bulk_data = [
        {"index": {"_id": task_data["uuid"], "_index": ES_INDEX_NAME_REAL}},
        task_data,
    ]
    res = conn.bulk(index=ES_INDEX_NAME_REAL, doc_type=DOC_TYPE, body=bulk_data)
    assert res["errors"] is False

    encounter_data = _make_index_item("Encounter")
    bulk_data = [
        {"index": {"_id": encounter_data["uuid"], "_index": ES_INDEX_NAME_REAL}},
        encounter_data,
    ]
    res = conn.bulk(index=ES_INDEX_NAME_REAL, doc_type=DOC_TYPE, body=bulk_data)
    assert res["errors"] is False

    careplan_data = _make_index_item("CarePlan")
    bulk_data = [
        {"index": {"_id": careplan_data["uuid"], "_index": ES_INDEX_NAME_REAL}},
        careplan_data,
    ]
    res = conn.bulk(index=ES_INDEX_NAME_REAL, doc_type=DOC_TYPE, body=bulk_data)
    assert res["errors"] is False

    documentreference_data = _make_index_item("DocumentReference")
    bulk_data = [
        {"index": {"_id": documentreference_data["uuid"], "_index": ES_INDEX_NAME_REAL}},
        documentreference_data,
    ]
    res = conn.bulk(index=ES_INDEX_NAME_REAL, doc_type=DOC_TYPE, body=bulk_data)
    assert res["errors"] is False

    conn.indices.refresh(index=ES_INDEX_NAME_REAL)


def _cleanup_es(conn, prefix=""):
    """RAW ES Connection"""
    for alias in (conn.cat.aliases()).splitlines():
        name, index = alias.split()[:2]
        if name[0] == "." or index[0] == ".":
            # ignore indexes that start with .
            continue
        if name.startswith(prefix):
            try:
                conn.indices.delete_alias(index, name)
                conn.indices.delete(index)
            except elasticsearch.exceptions.AuthorizationException:
                pass
    for index in (conn.cat.indices()).splitlines():
        _, _, index_name = index.split()[:3]
        if index_name[0] == ".":
            # ignore indexes that start with .
            continue
        if index_name.startswith(prefix):
            try:
                conn.indices.delete(index_name)
            except elasticsearch.exceptions.AuthorizationException:
                pass


class Postgresql(BaseImage):
    name = "postgresql"
    port = 5432

    def check(self):
        import psycopg2

        try:
            conn = psycopg2.connect(
                f"dbname=fhir_db user=postgres host={self.host} "
                f"port={self.get_port()}"
            )
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            cur.fetchone()
            cur.close()
            conn.close()
            return True
        except:  # noqa
            conn = None
            cur = None
        return False


pg_image = Postgresql()


def _init_fhirbase_structure(connection):
    """ """
    struc_file = FHIRBASE_STRUCTURE_DIR / "fhirbase-4.0.0.sql"
    with io.open(str(struc_file)) as fp:
        struc = fp.read()

    with connection.get_cursor(commit=True) as cursor:
        cursor.execute(struc)
