# _*_ coding: utf-8 _*_
from zope.interface import Attribute
from zope.interface import Interface


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class IEngine(Interface):
    """ """

    fhir_release = Attribute("FHIR Release")
    connection = Attribute("DB Connection")
    dialect = Attribute("Dialect")

    def execute():
        """Return"""

    def connect(**kw):
        """Return a new Connection object."""

    def wrapped_with_bundle():
        """ """


class IElasticsearchEngine(IEngine):
    """ """

    def get_index_name(context):
        """ """

    def build_security_query():
        """ """

    def calculate_field_index_name():
        """ """


class IEngineFactory(Interface):
    """Utility marker"""


class IElasticsearchEngineFactory(IEngineFactory):
    """ """
