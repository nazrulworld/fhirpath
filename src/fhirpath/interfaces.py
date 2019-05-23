# _*_ coding: utf-8 _*_
from zope.interface import Attribute
from zope.interface import Interface


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class IStorage(Interface):
    """ """

    _last_updated = Attribute("Last Updated")
    _write_locked = Attribute("Write Locked")
    _read_locaked = Attribute("Read Locked")

    def get(item):
        """ """

    def set(item, value):
        """ """

    def insert(item, value):
        """ """

    def delete(item):
        """ """

    def clear():
        """ """

    def exists(item):
        """ """

    def empty():
        """ """
    def total():
        """ """


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


class IEngine(Interface):
    """ """

    fhir_release = Attribute("FHIR Release")
    connection = Attribute("DB Connection")
    dialect = Attribute("Dialect")

    def create_query():
        """Return QueryBuilder"""

    def connect(**kw):
        """Return a new Connection object."""


class IConnection(Interface):
    """ """

    raw = Attribute("Raw connection underlaying DBAPI")

    def execute(query, **kwargs):
        """ """


class IEngineFactory(Interface):
    """ """
