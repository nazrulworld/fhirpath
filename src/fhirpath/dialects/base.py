# _*_ coding: utf-8 _*_
from zope.interface import implementer

from fhirpath.interfaces import IConnection
from fhirpath.interfaces import IDialect


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

    def compile(self, query):
        """ """
        raise NotImplementedError

    def pre_compile(self, query):
        """xxx: validation placeholder"""
        pass
