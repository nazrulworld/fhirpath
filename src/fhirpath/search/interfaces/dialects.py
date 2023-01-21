# _*_ coding: utf-8 _*_
from zope.interface import Attribute, Interface

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class IDialect(Interface):
    """ """

    _connection = Attribute("Connection from Engine")

    def bind(connection):  # lgtm[py/not-named-self]
        """ """

    def compile(query):  # lgtm[py/not-named-self]
        """ """

    def pre_compile(query):  # lgtm[py/not-named-self]
        """ """


class IIgnoreNestedCheck(Interface):
    """Marker interface"""
