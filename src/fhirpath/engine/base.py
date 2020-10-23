# _*_ coding: utf-8 _*_
import time
from abc import ABC
from collections import defaultdict, deque
import re
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
from fhirpath.thirdparty import Proxy

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

CONTAINS_INDEX_OR_FUNCTION = re.compile(r"[a-z09_]+(\[[0-9]+\])|(\([0-9]*\))$", re.I)
CONTAINS_INDEX = re.compile(r"[a-z09_]+\[[0-9]+\]$", re.I)
CONTAINS_FUNCTION = re.compile(r"[a-z09_]+\([0-9]*\)$", re.I)


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

    def filter(self, selects):
        if len(selects) > 0:
            new_body = EngineResultBody()
            for row in self.body:
                new_row = EngineResultRow()
                source = row[0]
                for fullpath in selects:
                    for path_ in fullpath.split("."):
                        source = _traverse_for_value(source, path_)
                        if source is None:
                            break
                    new_row.append(source)
                new_body.append(new_row)
            self.body = new_body

        return self

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
        assert search_param.type == "reference"
        assert isinstance(
            search_param.expression, str
        ), f"'expression' is not defined for search parameter {search_param.name}"
        ids: Dict = defaultdict(list)

        def browse(node, path):
            parts = path.split(".", 1)

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

        if not search_param.expression:
            raise Exception()

        # use ElementPath to parse fhirpath expressions like .where()
        path_element = ElementPath(search_param.expression)
        # remove the resource type from the path
        _, path = path_element._path.split(".", 1)
        for row in self.body:
            resource = row[0]
            ref_attribute = browse(resource, path)

            # if the searchparam expression contains .where() statement, skip references
            # that do not match the required resource type
            if (
                path_element._where
                and path_element._where.type == WhereConstraintType.T2
            ):
                ref_target_type = ref_attribute["reference"].split("/")[0]
                if path_element._where.value != ref_target_type:
                    continue

            if isinstance(ref_attribute, list):
                for r in ref_attribute:
                    append_ref(r)
            else:
                append_ref(ref_attribute)

        return ids

def navigate_indexed_path(source, path_):
    """ """
    parts = path_.split("[")
    p_ = parts[0]
    index = int(parts[1][:-1])
    value = source.get(p_, None)
    if value is None:
        return value

    try:
        return value[index]
    except IndexError:
        return None

def _traverse_for_value(source, path_):
    """Looks path_ is innocent string key, but may content expression, function."""
    if isinstance(source, dict):
        # xxx: validate path, not blindly sending None
        if CONTAINS_INDEX_OR_FUNCTION.search(path_) and CONTAINS_FUNCTION.match(
            path_
        ):
            raise ValidationError(
                f"Invalid path {path_} has been supllied!"
                "Path cannot contain function if source type is dict"
            )
        if CONTAINS_INDEX.match(path_):
            return navigate_indexed_path(source, path_)
        if path_ == "*":
            # TODO check if we can have other keys than resource
            return source[list(source.keys())[0]]

        return source.get(path_, None)

    elif isinstance(source, list):
        if not CONTAINS_FUNCTION.match(path_):
            raise ValidationError(
                f"Invalid path {path_} has been supllied!"
                "Path should contain function if source type is list"
            )
        parts = path_.split("(")
        func_name = parts[0]
        index = None
        if len(parts[1]) > 1:
            index = int(parts[1][:-1])
        if func_name == "count":
            return len(source)
        elif func_name == "first":
            return source[0]
        elif func_name == "last":
            return source[-1]
        elif func_name == "Skip":
            new_order = list()
            for idx, no in enumerate(source):
                if idx == index:
                    continue
                new_order.append(no)
            return new_order
        elif func_name == "Take":
            try:
                return source[index]
            except IndexError:
                return None
        else:
            raise NotImplementedError
    elif isinstance(source, (bytes, str)):
        if not CONTAINS_FUNCTION.match(path_):
            raise ValidationError(
                f"Invalid path {path_} has been supplied!"
                "Path should contain function if source type is list"
            )
        parts = path_.split("(")
        func_name = parts[0]
        index = len(parts[1]) > 1 and int(parts[1][:-1]) or None
        if func_name == "count":
            return len(source)
        else:
            raise NotImplementedError

    else:
        raise NotImplementedError
