# _*_ coding: utf-8 _*_
from zope.interface import Attribute, Interface

from .base import IBaseClass

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class IValuedClass(Interface):
    """Any class must have value attribute"""

    _value_assigned = Attribute("Flag if value assigned")
    value = Attribute("Value")


class IFqlClause(Interface):
    """ """

    empty = Attribute("Empty Flag")


class IBaseTerm(IBaseClass):
    """ """


class ITerm(IBaseTerm):
    """ """


class INonFhirTerm(IBaseTerm):
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


class IPathConstraint(Interface):
    """ """
