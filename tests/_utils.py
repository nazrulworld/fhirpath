# _*_ coding: utf-8 _*_
import datetime
import io
import json
import os
import pathlib
import subprocess
import uuid
import time

import pytz
from isodate import datetime_isoformat

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
DOC_TYPE = "_doc"

ES_INDEX_NAME = "fhirpath_elasticsearch_index"
ES_INDEX_NAME_REAL = "fhirpath_elasticsearch_index_1"


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


def load_organizations_data(conn, count=1):
    """ """
    added = 0

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


def _setup_es_index(conn):
    """ """
    body = {
        "settings": {
            "analysis": {
                "analyzer": {"path_analyzer": {"tokenizer": "path_tokenizer"}},
                "char_filter": {},
                "filter": {},
                "tokenizer": {
                    "path_tokenizer": {"delimiter": "/", "type": "path_hierarchy"}
                },
            }
        },
        "mappings": {
            "dynamic": False,
            "properties": {
                "access_roles": {"index": True, "store": True, "type": "keyword"},
                "access_users": {"index": True, "store": True, "type": "keyword"},
                "creation_date": {"store": True, "type": "date"},
                "depth": {"type": "integer"},
                "elastic_index": {"index": True, "store": True, "type": "keyword"},
                "id": {"index": True, "store": True, "type": "keyword"},
                "modification_date": {"store": True, "type": "date"},
                "p_type": {"index": True, "type": "keyword"},
                "parent_uuid": {"index": True, "store": True, "type": "keyword"},
                "path": {"analyzer": "path_analyzer", "store": True, "type": "text"},
                "tid": {"index": True, "store": True, "type": "keyword"},
                "title": {"index": True, "store": True, "type": "text"},
                "uuid": {"index": True, "store": True, "type": "keyword"},
            },
        },
    }

    org_mapping = fhir_resource_mapping("Organization")
    patient_mapping = fhir_resource_mapping("Patient")
    body["mappings"]["properties"]["organization_resource"] = org_mapping
    body["mappings"]["properties"]["patient_resource"] = patient_mapping

    conn.indices.create(ES_INDEX_NAME_REAL, body=body)
    conn.indices.refresh(index=ES_INDEX_NAME_REAL)


def _make_index_item(resource_type):
    """ """

    id_prefix = "2c1|"
    uuid_ = uuid.uuid4().hex
    now_time = datetime.datetime.now()
    now_time.replace(tzinfo=pytz.UTC)

    tpl = {
        "access_roles": [
            "guillotina.Reader",
            "guillotina.Reviewer",
            "guillotina.Owner",
            "guillotina.Editor",
            "guillotina.ContainerAdmin",
        ],
        "access_users": ["root"],
        "creation_date": datetime_isoformat(now_time),
        "depth": 2,
        "elastic_index": "{0}__{1}-{2}".format(
            ES_INDEX_NAME, resource_type.lower(), uuid_
        ),
        "id": None,
        "parent_uuid": "2c1a8a1403a743608aafc294b6e822af",
        "path": "/f001",
        "tid": 8,
        "title": "Burgers University Medical Center",
        "uuid": id_prefix + uuid_,
    }

    with open(str(FHIR_EXAMPLE_RESOURCES / (resource_type + ".json")), "r") as fp:
        data = json.load(fp)

    data["id"] = uuid_
    tpl["id"] = uuid_
    tpl["path"] = "/" + uuid_
    tpl[resource_type.lower() + "_resource"] = data
    if resource_type == "Organization":
        tpl["title"] = data["name"]
    else:
        raise NotImplementedError

    return tpl


def _load_es_data(conn):
    """ """
    organization_data = _make_index_item("Organization")
    bulk_data = [
        {"index": {"_id": organization_data["uuid"], "_index": ES_INDEX_NAME_REAL}},
        organization_data,
    ]
    res = conn.bulk(index=ES_INDEX_NAME_REAL, doc_type=DOC_TYPE, body=bulk_data)
    assert res["errors"] is False

    conn.indices.refresh(index=ES_INDEX_NAME_REAL)
