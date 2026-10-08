# _*_ coding: utf-8 _*_
import re
import time
from abc import ABC
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Pattern, Tuple

from zope.interface import implementer

from fhirpath.core import compile as fhirpath_compile
from fhirpath.enums import FHIR_VERSION
from ..exceptions import ValidationError
from ..fhirspec import SearchParameter
from ..interfaces import IEngine
from ..interfaces.engine import (
    IEngineResult,
    IEngineResultBody,
    IEngineResultHeader,
    IEngineResultRow,
)

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

# "Patient/123", "Patient/123/_history/2" or "http://example.org/fhir/Patient/123"
LITERAL_REFERENCE: Pattern = re.compile(
    r"(?:^|/)(?P<type>[A-Z][A-Za-z]+)/(?P<id>[A-Za-z0-9\-.]{1,64})"
    r"(?:/_history/[^/]+)?$"
)


def parse_literal_reference(reference: Any) -> Optional[Tuple[str, str]]:
    """``(resource type, id)`` of a literal reference (a ``Reference`` element,
    as a dict or model, or its ``reference`` string); ``None`` otherwise
    (contained ``#id`` references, logical references, canonicals...)."""
    if not isinstance(reference, str):
        if isinstance(reference, dict):
            reference = reference.get("reference")
        else:
            reference = getattr(reference, "reference", None)
    if not isinstance(reference, str):
        return None
    match = LITERAL_REFERENCE.search(reference)
    if match is None:
        return None
    return match.group("type"), match.group("id")


def resolve_literal_reference(reference: str, origin: Any = None) -> Optional[Dict]:
    """FHIRPath ``resolve()`` hook: a stub resource carrying the referenced type."""
    parsed = parse_literal_reference(reference)
    if parsed is None:
        return None
    return {"resourceType": parsed[0], "id": parsed[1]}


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

        # evaluate the search parameter's FHIRPath expression with the core engine;
        # ``resolve()`` (e.g. ``subject.where(resolve() is Patient)``) only needs the
        # target type, which literal references carry
        expression = fhirpath_compile(search_param.expression)
        for row in self.body:
            for reference in expression.evaluate(
                row[0], resolver=resolve_literal_reference
            ):
                parsed = parse_literal_reference(reference)
                if parsed is not None:
                    ids[parsed[0]].append(parsed[1])

        return ids
