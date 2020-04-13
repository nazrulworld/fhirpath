# _*_ coding: utf-8 _*_
import enum
import operator
from typing import Any
from typing import Callable
from typing import Text


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


class FHIR_VERSION(enum.Enum):
    """Release:str : Version:str """

    DEFAULT: str = "R4"
    STU3: str = "3.0.2"
    R4: str = "4.0.1"
    DSTU2: str = "1.0.2"


@enum.unique
class SortOrderType(enum.Enum):
    """ """

    ASC: Text = "asc"
    DESC: Text = "desc"


@enum.unique
class MatchType(enum.Enum):
    """ """

    ANY: Text = "ANY"
    ALL: Text = "ALL"
    ONE: Text = "ONE"
    NONE: Text = "NONE"


@enum.unique
class TermMatchType(enum.Enum):
    """ """

    EXACT: Text = "EXACT"
    STARTWITH: Text = "STARTWITH"
    ENDWITH: Text = "ENDWITH"
    FULLTEXT: Text = "FULLTEXT"


@enum.unique
class GroupType(enum.Enum):
    DECOUPLED: Text = "DECOUPLED"
    COUPLED: Text = "COUPLED"


@enum.unique
class WhereConstraintType(enum.Enum):
    """ """

    # normal key, value conditional
    T1: Text = "T1"
    # constraint certain FHIR Resource type
    T2: Text = "T2"
    # complex constraint with subpath
    T3: Text = "T3"


@enum.unique
class EngineQueryType(enum.Enum):
    """" """

    DDL: Text = "DDL"
    DML: Text = "DML"
    COUNT: Text = "COUNT"


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
