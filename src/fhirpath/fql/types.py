# _*_ coding: utf-8 _*_
import operator
from copy import copy

from zope.interface import implementer
from zope.interface import implementer_only

from fhirpath.enums import SortOrderType
from fhirpath.exceptions import ConstraintNotSatisfied
from fhirpath.exceptions import ValidationError
from fhirpath.interfaces import IFhirPrimitiveType
from fhirpath.types import EMPTY_VALUE
from fhirpath.utils import PathInfoContext
from fhirpath.utils import proxy

from .interfaces import IElementPath
from .interfaces import IExistsTerm
from .interfaces import IGroupTerm
from .interfaces import IInTerm
from .interfaces import IInTermValue
from .interfaces import IModel
from .interfaces import ISortTerm
from .interfaces import ITerm
from .interfaces import ITermValue


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def _constraint_value_assigned(obj):
    """ """
    _constraint_finalized(obj)

    if obj._value_assigned is True:
        raise ConstraintNotSatisfied(
            "Value already assigned to {0!r}".format(obj.__class__)
        )


def _constraint_finalized(obj):
    """ """
    if obj._finalized:
        raise ConnectionResetError(
            "Object from {0!r} is already in final state, "
            "means any modification been locked".format(obj.__class__)
        )


@implementer(ITerm)
class Term(object):
    """ """

    def __init__(self, path, value=EMPTY_VALUE):
        """ """
        # flag
        self._finalized = False
        self._value_assigned = False

        # Path Context
        self.path_context = None
        # eq, ne, lt, le, gt, ge
        self.comparison_operator = None
        # +,- (negetive, positive)
        self.unary_operator = None
        # and, or, xor
        self.arithmetic_operator = None

        self.value = Term.ensure_term_value(value)

        if ITerm.providedBy(path):
            self.__merge__(path)
        else:
            self.path = path

        if self.value is not EMPTY_VALUE:
            self._value_assigned = True

    def finalize(self, context):
        """ """
        _constraint_finalized(self)

        # xxx: find type using Context
        # May path as Resource Attribute
        # Do validation
        self.fhir_release = context.fhir_release
        pathname = str(self.path)
        self.path_context = proxy(
            PathInfoContext.context_from_path(pathname, context.fhir_release)
        )
        self.value.finalize(self.path_context)

        if self.arithmetic_operator is None:
            self.arithmetic_operator = operator.and_

        if self.unary_operator is None:
            self.unary_operator = operator.pos

        if self.comparison_operator is None:
            self.comparison_operator = operator.eq

        self.validate()

        self._finalized = True

    def clone(self):
        """ """
        return self.__copy__()

    def validate(self):
        """ """
        # xxx: required validate ```comparison_operator```
        # lt,le,gt,ge only for Date,DateTime, Interger, Float
        if IFhirPrimitiveType.implementedBy(self.path_context.type_class):
            if self.path_context.type_name not in (
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
                        self.comparison_operator.__name__, self.path_context.type_name
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
        _constraint_finalized(self)

        self.unary_operator = operator.pos
        return self.clone()

    def __neg__(self):
        """-self Unary minus sign"""
        _constraint_finalized(self)

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
        _constraint_value_assigned(self)

        raise NotImplementedError

    def __compare__(self, other):
        """ """
        _constraint_value_assigned(self)

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
        elif IInTermValue.providedBy(value):
            value = value.value
        elif value is not EMPTY_VALUE:
            value = [value]
        else:
            value = list()

        super(InTerm, self).__init__(path, value)

    def __add__(self, other):
        """ """
        if IInTermValue.providedBy(other):
            self.value.extend(other.value)

        elif isinstance(other, (list, tuple, set)):
            if isinstance(other, (tuple, set)):
                other = list(other)

            self.value.extend(Term.ensure_term_value(other))
        else:
            self.value.append(Term.ensure_term_value(other))

        return self.clone()

    def finalize(self, context):
        """ """
        self.value = InTermValue(self.value)
        super(InTerm, self).finalize(context)


@implementer_only(IExistsTerm)
class ExistsTerm(Term):
    """ """

    def __init_(se_lf, path):
        """Only Takes Path"""
        super(ExistsTerm, self).__init__(path)


@implementer(ITermValue)
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
        _constraint_finalized(self)

        self.unary_operator = operator.pos
        return self.clone()

    def __neg__(self):
        """-self Unary minus sign"""
        _constraint_finalized(self)

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

    def finalize(self, context):
        """context: PathInfoContext """
        _constraint_finalized(self)

        value = context.type_class(self.raw)

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


@implementer(IInTermValue)
class InTermValue(TermValue):
    """ """

    def __init__(self, value):
        """ """
        if isinstance(value, (tuple, list, set)):
            if isinstance(value, (tuple, set)):
                value = list(value)

        elif value is not None:
            value = [value]
        else:
            value = list()

        value = Term.ensure_term_value(value)

        super(InTermValue, self).__init__(value)

    def __add__(self, other):
        """ """
        if IInTermValue.providedBy(other):
            self.value.extend(other.value)

        elif isinstance(other, (list, tuple, set)):
            if isinstance(other, (tuple, set)):
                other = list(other)

            self.value.extend(Term.ensure_term_value(other))
        else:
            self.value.append(Term.ensure_term_value(other))

        return self.clone()


@implementer(IGroupTerm)
class GroupTerm(object):
    """ """

    def __init__(self, *terms):
        """ """
        # flag
        self._finalized = False

        # +,- (negetive, positive)
        self.unary_operator = None
        # and, or, xor
        self.arithmetic_operator = None
        # any|all|one
        self.match_operator = None

        self.terms = list()

        for term in terms:
            self.terms.append(ITerm(term))

    def __add__(self, other):
        """ """
        self._add(other)

    def __iadd__(self, other):
        """ """
        self._add(other)

    def _add(self, other):
        """ """
        _constraint_finalized(self)
        if ITerm.providedBy(other):
            self.terms.append(other)

        elif IGroupTerm.providedBy(other):

            if self.unary_operator is None and other.unary_operator:
                self.unary_operator = other.unary_operator
            if self.arithmetic_operator is None and other.arithmetic_operator:
                self.arithmetic_operator = other.arithmetic_operator
            if self.match_operator is None and other.match_operator:
                self.match_operator = other.match_operator

            self.terms.extend(other.terms)

    def finalize(self, engine):
        """ """
        for term in self.terms:
            term.finalize(engine)

        self._finalized = True


@implementer(ISortTerm)
class SortTerm(object):
    """ """

    order = None
    path = None

    def __init__(self, path, order=SortOrderType.ASC):
        """ """
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


class ModelFactory(type):
    """FHIR Model factory"""

    def __new__(cls, name, bases, attrs, **kwargs):
        super_new = super().__new__

        # xxx: customize module path?
        module = attrs.pop("__module__")
        new_attrs = {"__module__": module}
        classcell = attrs.pop("__classcell__", None)
        if classcell is not None:
            new_attrs["__classcell__"] = classcell

        new_class = super_new(cls, name, bases, new_attrs, **kwargs)

        # Attach Interface
        new_class = implementer(IModel)(new_class)

        return new_class

    def add_to_class(cls, name, value):
        """ """
        setattr(cls, name, value)


@implementer(IElementPath)
class ElementPath(object):
    """FHIR Resource path (dotted)
    1. Normalize any condition, casting, logic check"""

    def __init__(self, dotted_path):
        """ """
        self.raw = dotted_path
        self.parts = dotted_path.split(".")
        self._where = list()

    @property
    def star(self):
        """ """
        return self.raw == "*"

    @classmethod
    def from_el_path(cls, el_path):
        """ """
        el_path = IElementPath(el_path)
        raise NotImplementedError

    def __str__(self):
        """ """
        # for now raw
        if isinstance(self.raw, bytes):
            val = self.raw.decode("utf8", "strict")
        else:
            val = self.raw

        return val

    def __bytes__(self):
        """ """
        if isinstance(self.raw, str):
            val = self.raw.encode("utf8", "strict")
        else:
            val = self.raw
        return val
