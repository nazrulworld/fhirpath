# _*_ coding: utf-8 _*_
from zope.interface import implementer

from fhirpath.interfaces import IConnection

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


@implementer(IConnection)
class Connection:
    """ """

    def __init__(self, conn):
        """ """
        self._conn = conn

    @property
    def raw_connection(self):
        """ """
        return self._conn

    @classmethod
    def from_prepared(cls, conn):
        """Connection instance creation, using already prepared RAW connection"""
        # xxx: do any validation
        self = cls(conn)
        return self

    @classmethod
    def from_url(cls, url: str):
        """
        1.) may be use connector utilities
        2.) may be url parser
        """
        raise NotImplementedError

    @classmethod
    def from_config(cls, config: dict):
        """ """
        raise NotImplementedError

    @classmethod
    def is_async(cls):
        return False
