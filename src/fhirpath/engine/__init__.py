# _*_ coding: utf-8 _*_
"""Implementation, the medium result collected from ES server"""
from fhirpath.enums import FHIR_VERSION

from .base import Engine
from .base import EngineResult
from .base import EngineResultBody
from .base import EngineResultHeader
from .connection import Connection


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

__all__ = [
    "Connection",
    "Engine",
    "EngineResult",
    "EngineResultHeader",
    "EngineResultBody"
]


def create_engine():
    """For now we are using ES dialect"""
    engine = Engine(FHIR_VERSION.R4, connection_factory, dialect_factory)
    return engine


def create_engine_from_context():
    """ """


def dialect_factory(engine):
    """ """
    from fhirpath.dialects.elasticsearch import ElasticSearchDialect

    return ElasticSearchDialect()


def connection_factory(engine):
    """ """
    return Connection(None)
