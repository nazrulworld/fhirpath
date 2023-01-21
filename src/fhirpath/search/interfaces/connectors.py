# _*_ coding: utf-8 _*_
from zope.interface import Attribute, Interface

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class IConnection(Interface):
    """ """

    _conn = Attribute("Raw connection underlaying DBAPI")

    def raw_connection():  # lgtm[py/not-named-self]
        """return underlaying DBAPI, could be realtime connection from config"""

    def server_info():  # lgtm[py/not-named-self]
        """ """

    def execute(query, **kwargs):  # lgtm[py/not-named-self]
        """ """
