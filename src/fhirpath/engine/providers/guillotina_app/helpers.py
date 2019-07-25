# _*_ coding: utf-8 _*_
""" """
import json
import sys
from typing import Union

from guillotina.configure.config import reraise
from zope.interface import Invalid

from fhirpath.storage import MemoryStorage
from fhirpath.types import EMPTY_VALUE


__docformat__ = "restructuredtext"

NoneType = type(None)

EMPTY_STRING = ""
FHIR_ES_MAPPINGS_CACHE = MemoryStorage()


def parse_json_str(str_val: str, encoding: str = "utf-8") -> Union[dict, NoneType]:
    """ """
    if str_val in (EMPTY_VALUE, EMPTY_STRING, None):
        # No parsing for empty value
        return None
    try:
        json_dict = json.loads(str_val, encoding=encoding)
    except ValueError as exc:
        msg = "Invalid JSON String is provided!\n{0!s}".format(exc)
        t, v, tb = sys.exc_info()
        try:
            reraise(Invalid(msg), None, tb)
        finally:
            del t, v, tb

    return json_dict


# def fhir_resource_mapping(resource_type: str, cache: bool = True) -> dict:
#     """"""
#     if resource_type in FHIR_ES_MAPPINGS_CACHE and cache:

#         return FHIR_ES_MAPPINGS_CACHE[resource_type]

#     try:
#         FHIR_RESOURCE_LIST[resource_type.lower()]
#     except KeyError:
#         msg = f"{resource_type} is not valid FHIR resource type"

#         t, v, tb = sys.exc_info()
#         try:
#             reraise(Invalid(msg), None, tb)
#         finally:
#             del t, v, tb
#     mapping_json = FHIR_RESOURCE_MAPPING_DIR / f"{resource_type}.mapping.json"

#     if not mapping_json.exists():

#         warnings.warn(
#             f"Mapping for {resource_type} is currently not supported,"
#             " default Resource's mapping is used instead!",
#             UserWarning,
#         )

#         return fhir_resource_mapping("Resource", cache=True)

#     with io.open(str(mapping_json), "r", encoding="utf8") as f:

#         mapping_dict = ujson.load(f)
#         # xxx: validate mapping_dict['meta']['profile']?

#         FHIR_ES_MAPPINGS_CACHE[resource_type] = mapping_dict["mapping"]

#     return FHIR_ES_MAPPINGS_CACHE[resource_type]
