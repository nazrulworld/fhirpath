# _*_ coding: utf-8 _*_
from zope.interface import Attribute
from zope.interface import Interface


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class IConnection(Interface):
    """ """

    _conn = Attribute("Raw connection underlaying DBAPI")

    def raw_connection():
        """return underlaying DBAPI, could be realtime connection from config"""

    def server_info():
        """ """

    def execute(query, **kwargs):
        """ """
