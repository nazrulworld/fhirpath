# _*_ coding: utf-8 _*_
from fhirpath.exceptions import ConstraintNotSatisfied

from .interfaces import IBaseClass, IValuedClass

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


def required_value_not_assigned(obj: object) -> None:
    """ """
    required_not_finalized(obj)
    obj = IValuedClass(obj)

    if obj._value_assigned is True:
        raise ConstraintNotSatisfied(
            "Value already assigned to {0!r}".format(obj.__class__)
        )


def required_not_finalized(obj: object) -> None:
    """ """
    obj = IBaseClass(obj)

    if obj._finalized:
        raise ConnectionResetError(
            "Object from {0!r} is already in final state, "
            "means any modification been locked".format(obj.__class__)
        )


def required_from_resource(obj: object) -> None:
    """ """
    if len(obj._from) == 0:  # type: ignore
        raise ConstraintNotSatisfied(
            "`_from` (resource must be provided first!) {0!r}".format(obj.__class__)
        )


def required_finalized(obj: object) -> None:
    """ """
    obj = IBaseClass(obj)

    if not obj._finalized:
        raise ConnectionResetError(
            "Object from {0!r} must be in final state, ".format(obj.__class__)
        )
