# _*_ coding: utf-8 _*_
import typing

from zope.interface import implementer

from .enums import FHIR_VERSION
from .interfaces import IModel
from .utils import lookup_fhir_class

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

    @staticmethod
    def create(
        resource_type: typing.Text, fhir_release: FHIR_VERSION = FHIR_VERSION.DEFAULT
    ):
        """ """
        model = lookup_fhir_class(resource_type, fhir_release)
        if not IModel.implementedBy(model):
            implementer(IModel)(model)

        return model
