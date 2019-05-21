# _*_ coding: utf-8 _*_
from zope.interface import Attribute
from zope.interface import Interface


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class IFqlClause(Interface):
    """ """
    empty = Attribute("Empty Flag")


class IModel(Interface):
    """ """


class ITerm(Interface):
    """ """


class IGroupTerm(ITerm):
    """ """


class IInTerm(ITerm):
    """ """


class IExistsTerm(ITerm):
    """ """


class ITermValue(Interface):
    """ """


class IElementPath(Interface):
    """ """


class ISortTerm(Interface):
    """ """

    order = Attribute("Sort Order")
    path = Attribute("Element Path")


class IQuery(Interface):
    """ """
    fhir_release = Attribute("FHIR Release Name")


class ISearchContext(Interface):
    """ """


class IQueryBuilder(Interface):
    """ """

    context = Attribute("Fhir Query Context")
    finalized = Attribute("Is Finalized")

    def finalize(context=None):
        """ """

    def bind(context):
        """ """


class IQueryResult(Interface):
    """ """

    def fetchall():
        """ """

    def single():
        """ """

    def first():
        """ """

    def last():
        """ """

    def tail():
        """ """

    def skip():
        """ """

    def take():
        """ """

    def count():
        """ """

    def empty():
        """ """
