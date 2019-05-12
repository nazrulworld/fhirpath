# _*_ coding: utf-8 _*_
from zope.interface import Attribute
from zope.interface import Interface


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class ISearch(Interface):
    """ """


class ISearchContext(Interface):
    """ """


class IFhirPrimitiveType(Interface):
    """ """

    __visit_name__ = Attribute("visit name")
    __regex__ = Attribute("Regex")

    def to_python():
        """ """
    def to_json():
        """ """
