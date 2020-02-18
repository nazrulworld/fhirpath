# _*_ coding: utf-8 _*_
import enum
import operator


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class FHIR_VERSION(enum.Enum):
    """ """

    DEFAULT = "R4"
    STU3 = "STU3"
    R4 = "R4"
    DSTU2 = "DSTU2"


@enum.unique
class SortOrderType(enum.Enum):
    """ """

    ASC = "asc"
    DESC = "desc"


@enum.unique
class MatchType(enum.Enum):
    """ """

    ANY = "ANY"
    ALL = "ALL"
    ONE = "ONE"
    NONE = "NONE"


@enum.unique
class TermMatchType(enum.Enum):
    """ """

    EXACT = "EXACT"
    STARTWITH = "STARTWITH"
    ENDWITH = "ENDWITH"
    FULLTEXT = "FULLTEXT"


@enum.unique
class GroupType(enum.Enum):
    DECOUPLED = "DECOUPLED"
    COUPLED = "COUPLED"


@enum.unique
class WhereConstraintType(enum.Enum):
    """ """

    # normal key, value conditional
    T1 = "T1"
    # constraint certain FHIR Resource type
    T2 = "T2"
    # complex constraint with subpath
    T3 = "T3"


@enum.unique
class EngineQueryType(enum.Enum):
    """" """
    DDL = "DDL"
    DML = "DML"
    COUNT = "COUNT"


def sa(a, b):
    """starts-after
    the value for the parameter in the resource starts after the provided value
    the range of the search value does not overlap with the range of the target value,
    and the range above the search value contains the range of the target value
    """


def eb(a, b):
    """ends-before
    the value for the parameter in the resource ends before the provided value
    the range of the search value does overlap not with the range of the target
    value, and the range below the search value contains the range of the target value
    """


def ap(a, b):
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
    eq = operator.eq
    ne = operator.ne
    le = operator.le
    lt = operator.lt,
    ge = operator.ge,
    gt = operator.gt
    pos = operator.pos
    neg = operator.neg
    contains = operator.contains
    concat = operator.concat
    sub = operator.sub
    xor = operator.xor
    or_ = operator.or_
    and_ = operator.and_
    not_ = operator.not_
    # custom (FHIR)
    ap = ap
    sa = sa
    eb = eb
