# _*_ coding: utf-8 _*_
import time
from abc import ABC
from collections import deque, defaultdict
from typing import Dict, List

from zope.interface import implementer

from fhirpath.enums import FHIR_VERSION
from fhirpath.interfaces import IEngine
from fhirpath.interfaces.engine import (
    IEngineResult,
    IEngineResultBody,
    IEngineResultHeader,
    IEngineResultRow,
)
from fhirpath.fhirspec import SearchParameter
from fhirpath.query import Query
from fhirpath.thirdparty import Proxy
from fhirpath.exceptions import ValidationError

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

    def create_query(self):
        """ """
        return Query.with_engine(self.__proxy__())

    def create_connection(self, factory):
        """ """
        self.connection = factory(self)

    def create_dialect(self, factory):
        """ """
        self.dialect = factory(self)

    def before_execute(self, query):
        """Hook: before execution of query"""
        pass

    def __proxy__(self):
        """ """
        return EngineProxy(self)


class EngineProxy(Proxy):
    """ """

    def __init__(self, engine):
        """ """
        obj = IEngine(engine)
        super(EngineProxy, self).__init__()
        # xxx: more?
        self.initialize(obj)


@implementer(IEngineResultHeader)
class EngineResultHeader(object):
    """ """

    total = None
    raw_query = None
    generated_on = None
    selects = None

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
        self, header: EngineResultHeader, body: EngineResultBody,
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
                    "failed to extract IDs from EngineResult: missing resourceType in resource"
                )
            ids[resource_type].append(resource_id)
        return ids

    def extract_references(self, search_param: SearchParameter) -> Dict[str, List[str]]:
        """Takes a search parameter as input and extract all targeted references

        Returns a dict like:
        {"Patient": ["list", "of", "referenced", "patient", "ids"], "Observation": []}
        """
        assert search_param.type == "reference"
        ids: Dict = defaultdict(list)

        def browse(node, path):
            parts = path.split(".", 1)

            # FIXME: we don't handle resolving reference to check their types yet.
            if parts[0].startswith("where("):
                parts = parts[1:]

            if len(parts) == 0:
                return node
            elif len(parts) == 1:
                return node[parts[0]]
            else:
                return browse(node[parts[0]], parts[1])

        def append_ref(ref_attr):
            if "reference" not in ref_attr:
                raise ValidationError(f"attribute {ref_attr} is not a Reference")
            # FIXME: this does not work with references using absolute URLs
            referenced_resource, _id = ref_attr["reference"].split("/")
            ids[referenced_resource].append(_id)

        _, path = search_param.expression.split(".", 1)
        for row in self.body:
            ref_attribute = browse(row[0], path)
            if isinstance(ref_attribute, list):
                for r in ref_attribute:
                    append_ref(r)
            else:
                append_ref(ref_attribute)
        return ids
