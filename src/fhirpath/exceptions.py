# _*_ coding: utf-8 _*_
from zope.interface import Invalid

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class ConstraintNotSatisfied(Invalid):
    """ """


class ValidationError(ConstraintNotSatisfied):
    """ """


class MultipleResultsFound(Invalid):
    """ """


class NoResultFound(Invalid):
    """ """
