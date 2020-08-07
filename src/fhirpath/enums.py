# _*_ coding: utf-8 _*_
import enum
import operator
from typing import Any, Callable

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


class FHIR_VERSION(enum.Enum):
    """Release:str : Version:str """

    DEFAULT: str = "R4"
    STU3: str = "3.0.2"
    R4: str = "4.0.1"
    DSTU2: str = "1.0.2"

    @staticmethod
    def normalize(item):
        """ """
        if item == FHIR_VERSION.DEFAULT:
            item = getattr(FHIR_VERSION, item.value)
        return item


@enum.unique
class SortOrderType(enum.Enum):
    """ """

    ASC: str = "asc"
    DESC: str = "desc"


@enum.unique
class MatchType(enum.Enum):
    """ """

    ANY: str = "ANY"
    ALL: str = "ALL"
    ONE: str = "ONE"
    NONE: str = "NONE"


@enum.unique
class TermMatchType(enum.Enum):
    """ """

    EXACT: str = "EXACT"
    STARTWITH: str = "STARTWITH"
    ENDWITH: str = "ENDWITH"
    FULLTEXT: str = "FULLTEXT"


@enum.unique
class GroupType(enum.Enum):
    DECOUPLED: str = "DECOUPLED"
    COUPLED: str = "COUPLED"


@enum.unique
class WhereConstraintType(enum.Enum):
    """ """

    # normal key, value conditional
    T1: str = "T1"
    # constraint certain FHIR Resource type
    T2: str = "T2"
    # complex constraint with subpath
    T3: str = "T3"


@enum.unique
class EngineQueryType(enum.Enum):
    """" """

    DDL: str = "DDL"
    DML: str = "DML"
    COUNT: str = "COUNT"


def sa(a: Any, b: Any) -> Any:
    """starts-after
    the value for the parameter in the resource starts after the provided value
    the range of the search value does not overlap with the range of the target value,
    and the range above the search value contains the range of the target value
    """
    pass


def eb(a: Any, b: Any) -> Any:
    """ends-before
    the value for the parameter in the resource ends before the provided value
    the range of the search value does overlap not with the range of the target
    value, and the range below the search value contains the range of the target value
    """


def ap(a: Any, b: Any) -> Any:
    """approximately
    the value for the parameter in the resource is approximately the same
    to the provided value. Note that the recommended value for the approximation
    is 10% of the stated value (or for a date, 10% of the gap between now and the date),
    but systems may choose other values where appropriate
    """


@enum.unique
class OPERATOR(enum.Enum):
    """ """

    # built-in
    eq: Callable = operator.eq
    ne: Callable = operator.ne
    le: Callable = operator.le
    lt: Callable = operator.lt
    ge: Callable = operator.ge
    gt: Callable = operator.gt
    pos: Callable = operator.pos
    neg: Callable = operator.neg
    contains: Callable = operator.contains
    concat: Callable = operator.concat
    sub: Callable = operator.sub
    xor: Callable = operator.xor
    or_: Callable = operator.or_
    and_: Callable = operator.and_
    not_: Callable = operator.not_
    # custom (FHIR)
    ap: Callable = ap
    sa: Callable = sa
    eb: Callable = eb
