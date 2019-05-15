# _*_ coding: utf-8 _*_
import operator

from fhirpath.utils import reraise

from .types import InTerm
from .types import SortTerm
from .types import Term
from .types import TermValue


__author__ = "Md Nazrul Islam <email2nazrul>"


# API functions
def T_(path, value=None):
    """ """
    term = Term(path=path, value=value)
    return term


def V_(value):
    """ """
    val = TermValue(value)
    return val


def exists_(path):
    """ """
    term = T_(path=path)
    term.unary_operator = operator.pos
    return term


def not_exists_(path):
    """ """
    term = T_(path=path)
    term.unary_operator = operator.neg
    return term


def and_(path, value=None):
    """ """
    term = T_(path, value)
    term.arithmetic_operator = operator.and_

    return term


def or_(path, value=None):
    """ """
    term = T_(path, value)
    term.arithmetic_operator = operator.or_

    return term


def not_(path, value=None):
    """ """
    term = T_(path, value)
    term.comparison_operator = operator.not_

    return term


def in_(path, values):
    """ """
    term = InTerm(path, values)
    return term


def sort_(path, order=None):
    """ """
    sort_term = SortTerm(path)
    if order:
        sort_term.order = order

    return sort_term


def fql(obj):
    """ """
    try:
        func = getattr(obj, "__fql__")
        try:
            getattr(func, "__self__")
        except AttributeError:
            reraise(
                ValueError, "__fql__ is not bound method, make sure class initialized!"
            )

        return func()
    except AttributeError:
        raise AttributeError("Object must have __fql__ method available")
