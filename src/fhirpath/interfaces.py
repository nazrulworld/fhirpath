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


class IPathInfoContext(Interface):
    """ """

    fhir_release = Attribute("FHIR Release")
    prop_name = Attribute("Property Name")
    prop_original = Attribute("Original propety name")
    type_name = Attribute("Type Name")
    type_class = Attribute("Type Class")
    optional = Attribute("Optional")
    multiple = Attribute("Multiple")
