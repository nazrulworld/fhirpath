# _*_ coding: utf-8 _*_
from zope.interface import implementer

from fhirpath.interfaces import IConnection, IDialect

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


@implementer(IDialect)
class DialectBase(object):
    """ """

    def __init__(self, connection=None):
        """ """
        self._connection = connection and IConnection(connection) or None

    def bind(self, connection):
        """ """
        self._connection = IConnection(connection)

    def compile(self, query, mapping=None, root_replacer=None, **kwargs):
        """ """
        raise NotImplementedError

    def pre_compile(self, query):
        """xxx: validation placeholder"""
        pass

    @staticmethod
    def is_fhir_primitive_type(klass):
        """ """
        if klass is bool:
            return True
        else:
            return klass.is_primitive()
