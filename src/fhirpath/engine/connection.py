# _*_ coding: utf-8 _*_
from zope.interface import implementer

from fhirpath.interfaces import IConnection
from fhirpath.thirdparty import Proxy


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


@implementer(IConnection)
class Connection(object):
    """ """


class ConnectionProxy(Proxy):
    """ """
