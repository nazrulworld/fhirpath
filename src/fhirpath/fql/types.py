# _*_ coding: utf-8 _*_
import ast
import operator
import re
from collections import deque
from copy import copy

from zope.interface import implementer
from zope.interface import implementer_only

from fhirpath.enums import GroupType
from fhirpath.enums import MatchType
from fhirpath.enums import SortOrderType
from fhirpath.enums import WhereConstraintType
from fhirpath.exceptions import ValidationError
from fhirpath.interfaces import IFhirPrimitiveType
from fhirpath.types import EMPTY_VALUE
from fhirpath.utils import PathInfoContext
from fhirpath.utils import proxy
from fhirpath.utils import unwrap_proxy

from .constraints import required_finalized
from .constraints import required_not_finalized
from .constraints import required_value_not_assigned
from .interfaces import IElementPath
from .interfaces import IExistsGroupTerm
from .interfaces import IExistsTerm
from .interfaces import IFqlClause
from .interfaces import IGroupTerm
from .interfaces import IInTerm
from .interfaces import IPathConstraint
from .interfaces import ISortTerm
from .interfaces import ITerm
from .interfaces import ITermValue
from .interfaces import IValuedClass


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

has_dot_as = re.compile(r"\.as\([a-z]+\)$", re.I | re.U)
has_dot_is = re.compile(r"\.is\([a-z]+\)$", re.I | re.U)
has_dot_where = re.compile(r"\.where\([a-z\=\'\"\(\)\s\-]+\)", re.I | re.U)


@implementer(IFqlClause)
class FqlClause(deque):
    """ """

    @property
    def empty(self):
        """ """
        return len(self) == 0


class WhereClause(FqlClause):
    """ """


class SelectClause(FqlClause):
    """ """


class FromClause(FqlClause):
    """ """


class SortClause(FqlClause):
    """ """


@implementer(IFqlClause)
class LimitClause(object):
    """ """

    __slots__ = ("_limit", "_offset")

    def __init__(self):
        """ """
        object.__setattr__(self, "_limit", None)
        object.__setattr__(self, "_offset", None)

    def _get_limit(self):
        """ """
        return self._limit

    def _set_limit(self, value):
        """ """
        self._limit = int(value)

    limit = property(_get_limit, _set_limit)

    def _get_offset(self):
        """ """
        return self._offset

    def _set_offset(self, value):
        """ """
        self._offset = int(value)

    offset = property(_get_offset, _set_offset)

    @property
    def empty(self):
        """ """
        return self._limit is None


@implementer(ITerm, IValuedClass)
class Term(object):
    """ """

    def __init__(self, path, value=EMPTY_VALUE):
        """ """
        # flag
        self._finalized = False
        self._value_assigned = False

        # eq, ne, lt, le, gt, ge
        self.comparison_operator = None
        # +,- (negetive, positive)
        self.unary_operator = None
        # and, or, xor
        self.arithmetic_operator = None

        self.value = Term.ensure_term_value(value)

        if ITerm.providedBy(path):
            self.__merge__(path)
        elif isinstance(path, str):
            self.path = ElementPath.from_el_path(path)
        else:
            self.path = path

        if self.value is not EMPTY_VALUE:
            self._value_assigned = True

    def _finalize(self, context):
        """ """
        required_not_finalized(self)

        # xxx: find type using Context
        # May path as Resource Attribute
        # Do validation
        self.fhir_release = context.fhir_release
        if not self.path.is_finalized():
            self.path.finalize(context)

        if self.arithmetic_operator is None:
            self.arithmetic_operator = operator.and_

        if self.unary_operator is None:
            self.unary_operator = operator.pos

        if self.comparison_operator is None:
            self.comparison_operator = operator.eq

        self.validate()

    def finalize(self, context):
        """ """
        self._finalize(context)
        if not self.value.is_finalized():
            self.value.finalize(self.path)

        self._finalized = True

    def clone(self):
        """ """
        return self.__copy__()

    def validate(self):
        """ """
        # xxx: required validate ```comparison_operator```
        # lt,le,gt,ge only for Date,DateTime, Interger, Float
        if IFhirPrimitiveType.implementedBy(self.path.context.type_class):
            if self.path.context.type_name not in (
                "integer",
                "decimal",
                "instant",
                "date",
                "dateTime",
                "time",
                "unsignedInt",
                "positiveInt",
            ) and self.comparison_operator in (
                operator.lt,
                operator.le,
                operator.gt,
                operator.ge,
            ):
                raise ValidationError(
                    "Operator '{0!s}' is allowed for value type '{1!s}'".format(
                        self.comparison_operator.__name__, self.path.context.type_name
                    )
                )
        else:
            # don't have usecase yet!
            raise NotImplementedError

    @staticmethod
    def ensure_term_value(value):
        """ """
        if value is EMPTY_VALUE or ITermValue.providedBy(value):
            return value

        if isinstance(value, list):
            value = list([Term.ensure_term_value(val) for val in value])
        else:
            value = TermValue(value)

        return value

    def __copy__(self):
        """ """
        newone = type(self).__new__(type(self))
        newone.__dict__.update(self.__dict__)

        # static properties
        newone._finalized = self._finalized
        newone._value_assigned = self._value_assigned

        newone.comparison_operator = self.comparison_operator
        newone.unary_operator = self.unary_operator
        newone.arithmetic_operator = self.arithmetic_operator

        # !important to copy
        newone.value = copy(self.value)
        newone.path = copy(self.path)

        return newone

    def __pos__(self):
        """+self Unary plus sign"""
        required_not_finalized(self)

        self.unary_operator = operator.pos
        return self.clone()

    def __neg__(self):
        """-self Unary minus sign"""
        required_not_finalized(self)

        self.unary_operator = operator.neg

        return self.clone()

    def __invert__(self):
        """~self Bitwise inversion"""
        raise NotImplementedError

    def __ne__(self, other):
        """Represent != """
        self.__compare__(other)
        self.comparison_operator = operator.ne

        return self.clone()

    def __eq__(self, other):
        """Represent =="""
        self.__compare__(other)
        self.comparison_operator = operator.eq

        return self.clone()

    def __le__(self, other):
        """Represent less than le """
        self.__compare__(other)
        self.comparison_operator = operator.le

        return self.clone()

    def __lt__(self, other):
        """ """
        self.__compare__(other)
        self.comparison_operator = operator.lt

        return self.clone()

    def __ge__(self, other):
        """ """
        self.__compare__(other)
        self.comparison_operator = operator.ge

        return self.clone()

    def __gt__(self, other):
        """ """
        self.__compare__(other)
        self.comparison_operator = operator.gt

        return self.clone()

    # Non standard
    def __merge__(self, other):
        """ """
        required_value_not_assigned(self)

        raise NotImplementedError

    def __compare__(self, other):
        """ """
        required_value_not_assigned(self)

        other = Term.ensure_term_value(other)
        self.value = other
        self._value_assigned = True
        if other.unary_operator is not None:
            self.unary_operator = other.unary_operator


@implementer(IInTerm)
class InTerm(Term):
    """The InTerm never influences by TermValue unary_operator!"""

    def __init__(self, path, value=EMPTY_VALUE):
        """ """
        if isinstance(value, (list, tuple, set)):
            if isinstance(value, (tuple, set)):
                value = list(value)
        elif value is not EMPTY_VALUE:
            value = [value]
        else:
            value = list()

        super(InTerm, self).__init__(path, value)

    def __add__(self, other):
        """ """
        if isinstance(other, (list, tuple, set)):
            if isinstance(other, (tuple, set)):
                other = list(other)

            self.value.extend(Term.ensure_term_value(other))
        else:
            self.value.append(Term.ensure_term_value(other))

        return self.clone()

    def __iadd__(self, other):
        """ """
        return self.__add__(other)

    def finalize(self, context):
        """ """
        self._finalize(context)

        [val.finalize(self.path) for val in self.value]

        self._finalized = True


@implementer_only(IExistsTerm)
class ExistsTerm(object):
    """ """

    def __init__(self, path):
        """Only Takes Path"""

        # flag
        self._finalized = False

        # Path Context
        self.context = None
        # +,- (negetive, positive)
        self.unary_operator = None

        if isinstance(path, str):
            self.path = ElementPath.from_el_path(path)
        else:
            self.path = path

        IElementPath(self.path)

    def finalize(self, context):
        """ """
        required_not_finalized(self)

        # xxx: find type using Context
        # May path as Resource Attribute
        # Do validation
        self.path.finalize(context)

        if self.unary_operator is None:
            self.unary_operator = operator.pos

        self._finalized = True

    def __copy__(self):
        """ """
        newone = type(self).__new__(type(self))
        newone.__dict__.update(self.__dict__)

        # static properties
        newone._finalized = self._finalized
        newone.unary_operator = self.unary_operator

        # !important to copy
        newone.path = copy(self.path)

        return newone

    def __pos__(self):
        """+self Unary plus sign"""
        required_not_finalized(self)

        self.unary_operator = operator.pos
        return self.clone()

    def __neg__(self):
        """-self Unary minus sign"""
        required_not_finalized(self)

        self.unary_operator = operator.neg

        return self.clone()

    def clone(self):
        """ """
        return self.__copy__()


@implementer(ITermValue, IValuedClass)
class TermValue(object):
    """ """

    def __init__(self, value):
        """ """
        self._finalized = False
        self.value = None
        self.raw = value
        # +,- (negetive, positive)
        self.unary_operator = None

    def __pos__(self):
        """+self Unary plus sign"""
        required_not_finalized(self)

        self.unary_operator = operator.pos
        return self.clone()

    def __neg__(self):
        """-self Unary minus sign"""
        required_not_finalized(self)

        self.unary_operator = operator.neg

        return self.clone()

    def __copy__(self):
        """ """
        newone = type(self).__new__(type(self))
        newone.__dict__.update(self.__dict__)

        newone.value = copy(self.value)
        newone.raw = copy(self.raw)
        newone._finalized = self._finalized
        # +,- (negetive, positive)
        newone.unary_operator = self.unary_operator

        return newone

    def clone(self):
        """ """
        return self.__copy__()

    def finalize(self, path):
        """context: PathInfoContext """
        required_not_finalized(self)
        path = IElementPath(path)
        value = path.context.type_class(self.raw)

        if IFhirPrimitiveType.providedBy(value):
            self.value = value.to_python()
        else:
            # xxx: support for other value type
            raise NotImplementedError

        self._finalized = True

    def __call__(self):
        """ """
        if not self._finalized:
            raise ValueError("Objectis not TermValue::finalize() yet!")
        return self.value

    def is_finalized(self):
        """ """
        return self._finalized


@implementer(IGroupTerm)
class GroupTerm(object):
    """ """

    def __init__(self, *terms, path=None):
        """ """
        # flag
        self._finalized = False

        # and, or, xor
        self.arithmetic_operator = None
        # any|all|one|none
        self.match_operator = None
        # COUPLED|DECOUPLED
        self.type = None

        self.terms = list()

        for term in terms:
            # could be GroupTerm | Term
            self.terms.append(ITerm(term))

        if isinstance(path, str):
            self.path = ElementPath.from_el_path(path)
        else:
            self.path = path

    def __add__(self, other):
        """ """
        return self._add(other)

    def __iadd__(self, other):
        """ """
        return self._add(other)

    def _add(self, other):
        """ """
        required_not_finalized(self)
        self.terms.append(ITerm(other))

        return self.clone()

    def clone(self):
        """ """
        return self.__copy__()

    def finalize(self, context):
        """ """
        if self.path is not None and (not self.path.is_finalized()):
            self.path.finalize(context)

        for term in self.terms:
            term.finalize(context)

        if self.match_operator is None:
            self.match_operator = MatchType.ANY

        if self.type is None:
            self.type = GroupType.COUPLED

        self._finalized = True

    def __copy__(self):
        """ """
        newone = type(self).__new__(type(self))
        newone.__dict__.update(self.__dict__)

        newone.terms = copy(self.terms)
        newone._finalized = self._finalized
        # and, or, xor
        newone.arithmetic_operator = self.arithmetic_operator
        # any|all|one
        newone.match_operator = self.match_operator

        return newone

    def match_all(self):
        """ """
        self.match_operator = MatchType.ALL
        return self.clone()

    def match_one(self):
        """ """
        self.match_operator = MatchType.ONE
        return self.clone()

    def match_any(self):
        """ """
        self.match_operator = MatchType.ANY
        return self.clone()


@implementer(IExistsGroupTerm)
class ExistsGroupTerm(object):
    """ """

    def __init__(self, *terms):
        """ """
        # flag
        self._finalized = False
        # any|all|one|none
        self.match_operator = None
        # COUPLED|DECOUPLED
        self.type = None

        self.terms = list()
        for term in terms:
            # could be GroupTerm | Term
            self.terms.append(IExistsTerm(term))

    def __add__(self, other):
        """ """
        return self._add(other)

    def __iadd__(self, other):
        """ """
        return self._add(other)

    def _add(self, other):
        """ """
        required_not_finalized(self)
        self.terms.append(IExistsTerm(other))

        return self.clone()

    def clone(self):
        """ """
        return self.__copy__()

    def finalize(self, context):
        """ """
        for term in self.terms:
            term.finalize(context)

        if self.match_operator is None:
            self.match_operator = MatchType.ANY

        if self.type is None:
            self.type = GroupType.COUPLED

        self._finalized = True

    def __copy__(self):
        """ """
        newone = type(self).__new__(type(self))
        newone.__dict__.update(self.__dict__)

        newone.terms = copy(self.terms)
        newone._finalized = self._finalized
        # any|all|one
        newone.match_operator = self.match_operator

        return newone

    def match_all(self):
        """ """
        self.match_operator = MatchType.ALL
        return self.clone()

    def match_one(self):
        """ """
        self.match_operator = MatchType.ONE
        return self.clone()

    def match_any(self):
        """ """
        self.match_operator = MatchType.ANY
        return self.clone()


@implementer(ISortTerm)
class SortTerm(object):
    """ """

    order = None
    path = None

    def __init__(self, path, order=SortOrderType.ASC):
        """ """
        self._finalized = False

        if not IElementPath.providedBy(path):
            path = ElementPath(path)
        self.path = path
        self.order = order

    def __pos__(self):
        """ """
        self.order = SortOrderType.ASC
        return copy(self)

    def __neg__(self):
        """ """
        self.order = SortOrderType.DESC
        return copy(self)

    def finalize(self, context):
        """ """
        required_not_finalized(self)

        if self.order is None:
            SortOrderType.ASC

        self._finalized = True


@implementer(IElementPath)
class ElementPath(object):
    """FHIR Resource path (dotted)
    1. Normalize any condition, casting, logic check"""

    def __init__(self, dotted_path: str):
        """ """
        self.context = None

        self._finalized = False
        self._path = None
        self._where = None
        self._is = None
        self._as = None
        self._raw = dotted_path

        self.parse()

    @property
    def star(self):
        """ """
        return self._raw == "*"

    @classmethod
    def from_el_path(cls, el_path):
        """ """
        el_path = ElementPath(el_path)
        # xxx: more things to do
        return el_path

    def __str__(self):
        """ """
        # for now raw
        if isinstance(self._path, bytes):
            val = self._path.decode("utf8", "strict")
        else:
            val = self._path

        return val

    def __bytes__(self):
        """ """
        if isinstance(self._path, str):
            val = self._path.encode("utf8", "strict")
        else:
            val = self._path
        return val

    def __call__(self, context):
        """ """
        if self._finalized is False:
            self.finalize(context)
        return str(self)

    def parse(self):
        """ """
        if self.star:
            self._path = self._raw
            return
        # xxx: more things soon
        if has_dot_as.search(self._raw):
            raise NotImplementedError
        elif has_dot_as.search(self._raw):
            raise NotImplementedError
        elif has_dot_where.search(self._raw):
            pos = self._raw.lower().find("where(")
            self._path = self._raw[0 : pos - 1]  # noqa: E203
            expr = self._raw[pos:]
            self._where = PathWhereConstraint.from_expression(expr)
        else:
            self._path = self._raw

    @property
    def path(self):
        """ """
        # xxx: some pre validations
        return self._path

    def validate(self, fhir_release):
        """ """
        if self.star:
            # no validation STAR
            return
        context = PathInfoContext.context_from_path(self._path, fhir_release)
        if context is None:
            raise ValidationError(
                "'{0}' is valid path for FHIR Release ''".format(
                    self._raw, fhir_release.value
                )
            )

    def finalize(self, context):
        """ """
        required_not_finalized(self)

        self.validate(context.fhir_release)
        # # xxx: more things to do
        self.context = proxy(
            PathInfoContext.context_from_path(self._path, context.fhir_release)
        )
        self._finalized = True

    def __copy__(self):
        """ """
        newone = type(self).__new__(type(self))
        newone.__dict__.update(self.__dict__)

        newone._finalized = self._finalized
        newone._path = self._path
        newone._raw = self._raw

        newone._where = copy(self._where)
        newone._is = copy(self._is)
        newone._as = copy(self._as)
        # already proxied, no need copy
        newone.context = self.context

        return newone

    def clone(self):
        """ """
        return self.__copy__()

    def __div__(self, other):
        """ """
        assert isinstance(other, str)
        required_finalized(self)

        obj = ElementPath.from_el_path("{0!s}.{1}".format(self, other))
        if self.is_finalized():
            # unwrap
            obj.finalize(unwrap_proxy(self.context))

        return obj

    def __truediv__(self, other):
        # https://stackoverflow.com/questions/21692065/python-class-div-issue
        return self.__div__(other)

    def is_finalized(self):
        """ """
        return self._finalized


@implementer(IPathConstraint)
class PathWhereConstraint(object):
    """ """

    def __init__(self, type_, name=None, value=None, subpath=None):
        """ """
        self.type = type_
        self.name = name
        self.value = value
        self.subpath = subpath

    @classmethod
    def from_expression(cls, expression):
        """ """
        if "resolve()" in expression:
            resource_type = expression.split("is")[-1].strip()[:-1]
            return cls(WhereConstraintType.T2, value=resource_type)
        else:
            parts = list(map(lambda x: x.strip(), expression.split("=")))
            name = parts[0][6:]
            if ")." in parts[1]:
                parts_ = list(parts[1].split(")."))
                value = ast.literal_eval(parts_[0].strip())
                subpath = parts_[1].strip()
                if name == "type":
                    name = None
                type_ = WhereConstraintType.T3
            else:
                value = ast.literal_eval(parts[1][:-1])
                subpath = None
                type_ = WhereConstraintType.T1

            return cls(type_=type_, name=name, value=value, subpath=subpath)
