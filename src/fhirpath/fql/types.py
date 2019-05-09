# _*_ coding: utf-8 _*_
import enum

from zope.interface import implementer

from .interfaces import IElementPath
from .interfaces import IModel


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


@enum.unique
class SortOrderType(enum):
    """ """

    ASC = "asc"
    DESC = "desc"


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
