# _*_ coding: utf-8 _*_
from zope.interface import implementer

from fhirpath.enums import FHIR_VERSION
from fhirpath.fql.queries import Query
from fhirpath.interfaces import IEngine
from fhirpath.thirdparty import Proxy


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


@implementer(IEngine)
class Engine(object):
    """Idea:
    1.) https://docs.sqlalchemy.org/en/13/core/connections.html#sqlalchemy.engine.Engine.connect
    2.) https://docs.sqlalchemy.org/en/13/core/connections.html#sqlalchemy.engine.Connection
    3.) Dialect could have raw connection, query compiler
    4.) Engine would have execute and result processing through provider, yes provider!
    """

    def __init__(self, fhir_release, dialect):
        """ """
        assert fhir_release in FHIR_VERSION
        self.fhir_release = fhir_release
        self.dialect = dialect

    def create_query(self):
        """ """
        return Query.with_engine(self.__proxy__(self))

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
