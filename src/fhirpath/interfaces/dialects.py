# _*_ coding: utf-8 _*_
from zope.interface import Attribute
from zope.interface import Interface


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class IDialect(Interface):
    """ """

    _connection = Attribute("Connection from Engine")

    def bind(connection):
        """ """

    def compile(query):
        """ """

    def pre_compile(query):
        """ """


class IIgnoreNestedCheck(Interface):
    """Marker interface"""
