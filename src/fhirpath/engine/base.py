# _*_ coding: utf-8 _*_
import time
from abc import ABC
from collections import deque

from zope.interface import implementer

from fhirpath.enums import FHIR_VERSION
from fhirpath.interfaces import IEngine
from fhirpath.interfaces.engine import (
    IEngineResult,
    IEngineResultBody,
    IEngineResultHeader,
    IEngineResultRow,
)
from fhirpath.query import Query
from fhirpath.thirdparty import Proxy

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


@implementer(IEngineResult)
class EngineResult(object):
    """ """

    __slot__ = ("header", "body")

    def __init__(self, header, body):
        """ """
        object.__setattr__(self, "header", header)
        object.__setattr__(self, "body", body)


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
