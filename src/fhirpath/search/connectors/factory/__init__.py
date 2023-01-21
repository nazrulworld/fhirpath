# _*_ coding: utf-8 _*_
from zope.interface import implementer

from fhirpath.utils import import_string

from ..interfaces import IURL, IConnectionFactory

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


@implementer(IConnectionFactory)
class ConnectionFactory:
    """ """

    def __init__(self, url, klass, **extra):
        """
        :param url: URL instance.

        :param klass: Connection Class or full path of string class.
        """
        if isinstance(url, (list, tuple)):
            self.url = [IURL(u) for u in url]
        else:
            self.url = IURL(url)

        if isinstance(klass, (str, bytes)):
            klass = import_string(klass)

        self.klass = klass
        self.wrapper_class = extra.pop("wrapper_class", None)
        self.extra = extra

    def wrap(self, raw_conn):
        """ """
        raise NotImplementedError
