# _*_ coding: utf-8 _*_
from zope.interface import Attribute
from zope.interface import Interface


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class IBaseClass(Interface):
    """ """

    _finalized = Attribute("Finalized Flag")

    def finalize(contex):
        """ """


class IValuedClass(Interface):
    """Any class must have value attribute"""

    _value_assigned = Attribute("Flag if value assigned")
    value = Attribute("Value")


class IFqlClause(Interface):
    """ """

    empty = Attribute("Empty Flag")


class ITerm(IBaseClass):
    """ """


class IGroupTerm(ITerm):
    """ """


class IExistsGroupTerm(IBaseClass):
    """ """


class IInTerm(ITerm):
    """ """


class IExistsTerm(ITerm):
    """ """


class ITermValue(IBaseClass):
    """ """


class IElementPath(IBaseClass):
    """ """


class ISortTerm(IBaseClass):
    """ """

    order = Attribute("Sort Order")
    path = Attribute("Element Path")


class IQuery(IBaseClass):
    """ """

    fhir_release = Attribute("FHIR Release Name")


class ISearchContext(Interface):
    """ """


class IQueryBuilder(IBaseClass):
    """ """

    context = Attribute("Fhir Query Context")

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


class IPathConstraint(Interface):
    """ """
