# _*_ coding: utf-8 _*_
import typing

from zope.interface import implementer

from .enums import FHIR_VERSION
from .fhirpath import FHIRPath
from .interfaces import IModel
from .utils import import_string
from .utils import lookup_fhir_class_path


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


class ModelFactory(type):
    """FHIR Model factory"""

    def __new__(cls, name, bases, attrs, **kwargs):
        super_new = super().__new__

        # xxx: customize module path?
        module = attrs.pop("__module__", cls.__module__)
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


class Model:
    """ """

    @classmethod
    def create(
        cls,
        resource_type: typing.Text,
        fhir_version: FHIR_VERSION = FHIR_VERSION.DEFAULT,
    ):
        """ """
        klass = import_string(
            typing.cast(
                typing.Text,
                lookup_fhir_class_path(resource_type, fhir_release=fhir_version),
            )
        )
        # xxx: should be cache?
        model = ModelFactory(f"{klass.__name__}Model", (klass, cls), {})

        return model

    def fpath(self, expression: str = None) -> FHIRPath:
        """ """
        if expression is None:
            return FHIRPath(self)

        raise NotImplementedError
