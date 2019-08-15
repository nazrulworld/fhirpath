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
