# _*_ coding: utf-8 _*_
from fhirpath.enums import OPERATOR, TermMatchType
from fhirpath.interfaces.fql import IGroupTerm, ITerm
from fhirpath.types import EMPTY_VALUE
from fhirpath.utils import reraise

from .types import (
    ExistsGroupTerm,
    ExistsTerm,
    GroupTerm,
    InTerm,
    NonFhirTerm,
    SortTerm,
    Term,
    TermValue,
)

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

__all__ = [
    "T_",
    "V_",
    "G_",
    "exists_",
    "not_exists_",
    "exists_group_",
    "and_",
    "or_",
    "xor_",
    "not_",
    "in_",
    "sort_",
    "fql",
]


# API functions
def T_(path, value=EMPTY_VALUE, match_type=None, non_fhir=False):  # noqa: E302
    """ """
    params = {"path": path, "value": value, "match_type": match_type}
    if non_fhir is False:
        term = Term(**params)
    else:
        term = NonFhirTerm(**params)
    return term


def V_(value):
    """ """
    val = TermValue(value)
    return val


def G_(*terms, path=None, type_=None):
    """ """
    group_term = GroupTerm(*terms, path=path)
    if type_ is not None:
        group_term.type = type_
    return group_term


def exists_(path):
    """ """
    if ITerm.providedBy(path):
        path_ = path.path
    else:
        path_ = path
    term = ExistsTerm(path_)
    term.unary_operator = OPERATOR.pos
    return term


def not_exists_(path):
    """ """
    return not_(exists_(path))


def exists_group_(*terms, type_=None):
    """ """
    g = ExistsGroupTerm(*terms)
    if type_ is not None:
        g.type = type_
    return g


def _prepare_term_or_group(path, value=EMPTY_VALUE):
    """ """
    term_or_group = EMPTY_VALUE
    if IGroupTerm.providedBy(path):
        term_or_group = path
    elif ITerm.providedBy(path):
        term_or_group = path
        if value is not EMPTY_VALUE:
            return term_or_group == value

    elif isinstance(path, str):
        term_or_group = T_(path, value)

    return term_or_group


def and_(path, value=EMPTY_VALUE):
    """ """
    term_or_group = _prepare_term_or_group(path, value=value)
    term_or_group.arithmetic_operator = OPERATOR.and_

    return term_or_group


def or_(path, value=EMPTY_VALUE):
    """ """
    term_or_group = _prepare_term_or_group(path, value=value)
    term_or_group.arithmetic_operator = OPERATOR.or_

    return term_or_group


def xor_(path, value=EMPTY_VALUE):
    """ """
    term_or_group = _prepare_term_or_group(path, value=value)
    term_or_group.arithmetic_operator = OPERATOR.xor

    return term_or_group


def not_(path, value=EMPTY_VALUE):
    """ """
    term_or_group = _prepare_term_or_group(path, value=value)
    term_or_group.unary_operator = OPERATOR.neg

    return term_or_group


def exact_(path, value=EMPTY_VALUE):
    """ """
    term = _prepare_term_or_group(path, value=value)
    ITerm(term).set_match_type(TermMatchType.EXACT)
    return term


def in_(path, values):
    """ """
    term = InTerm(path, values)
    return term


def not_in_(path, values):
    return not_(in_(path, values))


def sa_(path, value=EMPTY_VALUE):
    """ """
    term_or_group = _prepare_term_or_group(path, value)
    term_or_group.comparison_operator = OPERATOR.sa
    return term_or_group


def eb_(path, value=EMPTY_VALUE):
    """ """
    term_or_group = _prepare_term_or_group(path, value)
    term_or_group.comparison_operator = OPERATOR.eb
    return term_or_group


def contains_(path, value=EMPTY_VALUE):
    """ """
    term_or_group = _prepare_term_or_group(path, value)
    term_or_group.comparison_operator = OPERATOR.contains
    return term_or_group


def sort_(path, order=EMPTY_VALUE):
    """ """
    sort_term = SortTerm(path)
    if order is not EMPTY_VALUE:
        sort_term.order = order

    return sort_term


def fql(obj):
    """ """
    try:
        func = obj.__fql__
        try:
            func.__self__
        except AttributeError:
            reraise(
                ValueError, "__fql__ is not bound method, make sure class initialized!"
            )

        return func()
    except AttributeError:
        raise AttributeError("Object must have __fql__ method available")
