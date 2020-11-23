# _*_ coding: utf-8 _*_
import time
from abc import ABC
from collections import defaultdict, deque
from typing import Dict, List

from zope.interface import implementer

from fhirpath.enums import FHIR_VERSION, WhereConstraintType
from fhirpath.exceptions import ValidationError
from fhirpath.fhirspec import SearchParameter
from fhirpath.fql.types import ElementPath
from fhirpath.interfaces import IEngine
from fhirpath.interfaces.engine import (
    IEngineResult,
    IEngineResultBody,
    IEngineResultHeader,
    IEngineResultRow,
)

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


@implementer(IEngine)
class Engine(ABC):
    """Idea:
    # 1.) https://docs.sqlalchemy.org/en/13/core/\
    # connections.html#sqlalchemy.engine.Engine.connect
    2.) https://docs.sqlalchemy.org/en/13/core/\
        connections.html#sqlalchemy.engine.Connection
    3.) Dialect could have raw connection, query compiler
    4.) Engine would have execute and result processing through provider, yes provider!
    """

    def __init__(self, fhir_release, conn_factory, dialect_factory):
        """ """
        assert fhir_release in FHIR_VERSION
        self.fhir_release = FHIR_VERSION.normalize(fhir_release)

        self.create_connection(conn_factory)

        self.create_dialect(dialect_factory)

    def create_connection(self, factory):
        """ """
        self.connection = factory(self)

    def create_dialect(self, factory):
        """ """
        self.dialect = factory(self)

    def before_execute(self, query):
        """Hook: before execution of query"""
        pass

    @classmethod
    def is_async(cls):
        return False


@implementer(IEngineResultHeader)
class EngineResultHeader(object):
    """ """

    total = None
    raw_query = None
    generated_on = None
    elements = None

    def __init__(self, total, raw_query=None):
        """ """
        self.total = total
        self.raw_query = raw_query
        self.generated_on = time.time()


@implementer(IEngineResultBody)
class EngineResultBody(deque):
    """ """

    def append(self, value):
        """ """
        row = IEngineResultRow(value)
        deque.append(self, row)

    def add(self, value):
        """ """
        self.append(value)


@implementer(IEngineResultRow)
class EngineResultRow(list):
    """ """


@implementer(IEngineResult)
class EngineResult(object):
    """ """

    header: EngineResultHeader
    body: EngineResultBody

    def __init__(
        self,
        header: EngineResultHeader,
        body: EngineResultBody,
    ):
        """ """
        self.header = header
        self.body = body

    def extract_ids(self) -> Dict[str, List[str]]:
        ids: Dict = defaultdict(list)
        for row in self.body:
            resource_id = row[0].get("id")
            resource_type = row[0].get("resourceType")
            if not resource_id:
                raise ValidationError(
                    "failed to extract IDs from EngineResult: missing id in resource"
                )
            if not resource_type:
                raise ValidationError(
                    "failed to extract IDs from EngineResult: "
                    "missing resourceType in resource"
                )
            ids[resource_type].append(resource_id)
        return ids

    def extract_references(self, search_param: SearchParameter) -> Dict[str, List[str]]:
        """Takes a search parameter as input and extract all targeted references

        Returns a dict like:
        {"Patient": ["list", "of", "referenced", "patient", "ids"], "Observation": []}
        """
        if search_param.type != "reference":
            raise ValueError(
                "You cannot extract a reference for a search parameter "
                "that is not of type reference."
            )
        if not isinstance(search_param.expression, str):
            raise ValueError(
                f"'expression' is not defined for search parameter {search_param.name}"
            )

        ids: Dict = defaultdict(list)

        # use ElementPath to parse fhirpath expressions like .where()
        path_element = ElementPath(search_param.expression)

        def browse(node, path):
            parts = path.split(".", 1)

            if len(parts) == 0:
                return node
            elif parts[0] not in node:
                return None
            elif len(parts) == 1:
                return node[parts[0]]
            else:
                return browse(node[parts[0]], parts[1])

        def append_ref(ref_attr):
            # if the searchparam expression contains .where() statement, skip references
            # that do not match the required resource type
            if (
                path_element._where
                and path_element._where.type == WhereConstraintType.T2
            ):
                ref_target_type = ref_attr["reference"].split("/")[0]
                if path_element._where.value != ref_target_type:
                    return

            if "reference" not in ref_attr:
                return

            # FIXME: this does not work with references using absolute URLs
            referenced_resource, _id = ref_attr["reference"].split("/")
            ids[referenced_resource].append(_id)

        # remove the resource type from the path
        _, path = path_element._path.split(".", 1)
        for row in self.body:
            resource = row[0]
            ref_attribute = browse(resource, path)

            if ref_attribute is None:
                continue
            elif isinstance(ref_attribute, list):
                for r in ref_attribute:
                    append_ref(r)
            else:
                append_ref(ref_attribute)

        return ids
