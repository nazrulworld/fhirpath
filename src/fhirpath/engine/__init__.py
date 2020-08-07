# _*_ coding: utf-8 _*_
"""Implementation, the medium result collected from ES server"""
from fhirpath.connectors.connection import Connection
from fhirpath.enums import FHIR_VERSION

from .base import (
    Engine,
    EngineResult,
    EngineResultBody,
    EngineResultHeader,
    EngineResultRow,
)

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

__all__ = [
    "Connection",
    "Engine",
    "EngineResult",
    "EngineResultHeader",
    "EngineResultBody",
    "EngineResultRow",
]


def create_engine(conn):
    """For now we are using ES dialect"""
    engine = Engine(FHIR_VERSION.R4, lambda x: conn, dialect_factory)
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
