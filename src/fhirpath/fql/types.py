# _*_ coding: utf-8 _*_
import operator
from copy import copy

from zope.interface import implementer
from zope.interface import implementer_only

from fhirpath.enums import SortOrderType
from fhirpath.utils import PathInfoContext
from fhirpath.utils import proxy

from .interfaces import IElementPath
from .interfaces import IExistsTerm
from .interfaces import IInTerm
from .interfaces import IInTermValue
from .interfaces import IModel
from .interfaces import ISortTerm
from .interfaces import ITerm
from .interfaces import ITermValue


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class BaseType(object):
    """ """

    def __init__(self, max_=None, min_=None, type_code=None, type_=None):
        """ """
        self._max = max_
        self._min = min_
        self.__visit_name__ = type_code
        self._type = type_

    @property
    def is_array(self):
        """ """
        return self._max == "*"


@implementer(ITerm)
class Term(object):
    """ """

    def __init__(self, path, value=None):
        """ """
        # flag
        self.finalized = False

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
        self.path_context = None

    def finalize(self, context):
        """ """
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

    def clone(self):
        """ """
        return self.__copy__()

    def validate(self):
        """ """

    @staticmethod
    def ensure_term_value(value):
        """ """
        if value is None or ITermValue.provideBy(value):
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
        newone.finalized = self.finalized
        newone.comparison_operator = self.comparison_operator
        newone.unary_operator = self.unary_operator
        newone.arithmetic_operator = self.arithmetic_operator

        # !important to copy
        newone.value = copy(self.value)
        newone.path = copy(self.path)

        return newone

    def __pos__(self):
        """+self Unary plus sign"""
        self.unary_operator = operator.pos
        return self.clone()

    def __neg__(self):
        """-self Unary minus sign"""
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

    def __and__(self, other):
        """ Implements bitwise and using the & operator."""
        self.__compare__(other)
        self.comparison_operator = operator.eq
        self.arithmetic_operator = operator.and_

        return self.clone()

    def __or__(self, other):
        """Implements bitwise or using the | operator."""
        self.__compare__(other)
        self.comparison_operator = operator.eq
        self.arithmetic_operator = operator.or_

        return self.clone()

    def __xor__(self, other):
        """Implements bitwise xor using the ^ operator."""
        self.__compare__(other)
        self.comparison_operator = operator.eq
        self.arithmetic_operator = operator.xor

        return self.clone()

    # Non standard
    def __merge__(self, other):
        """ """
        raise NotImplementedError

    def __compare__(self, other):
        """ """
        other = Term.ensure_term_value(other)
        self.value = other
        if other.unary_operator is not None:
            self.unary_operator = operator.unary_operator


@implementer(IInTerm)
class InTerm(Term):
    """The InTerm never influences by TermValue unary_operator!"""

    def __init__(self, path, value=None):
        """ """
        if isinstance(value, (list, tuple, set)):
            if isinstance(value, (tuple, set)):
                value = list(value)
        elif IInTermValue.providedBy(value):
            value = value.value
        elif value is not None:
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

    def __init__(self, path):
        """Only Takes Path"""
        super(ExistsTerm, self).__init__(path)


@implementer(ITermValue)
class TermValue(object):
    """ """

    def __init__(self, value):
        """ """
        self.value = value
        # +,- (negetive, positive)
        self.unary_operator = None

    def clone(self):
        """ """

    def __pos__(self):
        """+self Unary plus sign"""
        self.unary_operator = operator.pos
        return self.clone()

    def __neg__(self):
        """-self Unary minus sign"""
        self.unary_operator = operator.neg

        return self.clone()

    def __copy__(self):
        """ """
        newone = type(self).__new__(type(self))
        newone.__dict__.update(self.__dict__)

        newone.value = copy(self.value)
        newone.type = copy(self.type)
        # +,- (negetive, positive)
        newone.unary_operator = self.unary_operator

        return newone

    def finalize(self, term):
        """ """
        # xxx: find type using Context
        # https://github.com/nazrulworld/fhir-parser\
        # /blob/d8c8871147031882011d5e497f3e99fc19863f27/fhirspec.py#L98
        # from there it is possible to calculate ValueType


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
