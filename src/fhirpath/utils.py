# _*_ coding: utf-8 _*_
import enum
import inspect
import pkgutil
import sys
from importlib import import_module
from typing import Union


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

NoneType = type(None)

FHIR_RESOURCE_CLASS_CACHE = dict(STU3=dict(), R4=dict())


@enum.unique
class FHIR_VERSION(enum.Enum):
    """ """

    DEFAULT = "R4"
    STU3 = "STU3"
    R4 = "R4"


def _reraise(tp, value, tb=None):
    if value is None:
        value = tp
    if value.__traceback__ is not tb:
        raise value.with_traceback(tb)
    raise value


def reraise(klass, msg=None, callback=None, **kw):
    """Reraise custom exception class"""
    if not issubclass(klass, Exception):
        raise RuntimeError(f"Class ``{klass}`` must be derrived from Exception class.")
    t, v, tb = sys.exc_info()
    msg = msg or str(v)
    try:
        instance = klass(msg, **kw)
        if callable(callback):
            instance = callback(instance)

        _reraise(instance, None, tb)
    finally:
        del t, v, tb


def import_string(dotted_path: str) -> type:
    """Shameless hack from django utils, please don't mind!"""
    module_path, class_name = None, None
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except (ValueError, AttributeError):

        t, v, tb = sys.exc_info()
        msg = "{0} doesn't look like a module path".format(dotted_path)
        try:
            reraise(ImportError(msg), None, tb)
        finally:
            del t, v, tb

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError:
        msg = 'Module "{0}" does not define a "{1}" attribute/class'.format(
            module_path, class_name
        )
        t, v, tb = sys.exc_info()
        try:
            return reraise(ImportError(msg), None, tb)
        finally:
            del t, v, tb


def fql(obj):
    """ """
    try:
        func = getattr(obj, "__fql__")
        try:
            getattr(func, "__self__")
        except AttributeError:
            reraise(
                ValueError, "__fql__ is not bound method, make sure class initialized!"
            )

        return func()
    except AttributeError:
        raise AttributeError("Object must have __fql__ method available")


def builder(func):
    """
    Decorator for wrapper "builder" functions.  These are functions on the
    Query class or other classes used for building queries which mutate the
    query and return self.  To make the build functions immutable, this decorator is
    used which will deepcopy the current instance.
    This decorator will return the return value of the inner function
    or the new copy of the instance.  The inner function does not need to return self.
    """
    import copy

    def _copy(self, *args, **kwargs):
        self_copy = copy.copy(self)
        result = func(self_copy, *args, **kwargs)

        # Return self if the inner function returns None.
        # This way the inner function can return something
        # different (for example when creating joins, a different builder is returned).
        if result is None:
            return self_copy

        return result

    return _copy


def lookup_fhir_class_path(
    resource_type: str,
    cache: bool = True,
    fhir_release: FHIR_VERSION = FHIR_VERSION.DEFAULT,
) -> Union[str, NoneType]:  # noqa: E999
    """This function finds FHIR resource model class (from fhir.resources) and
    return dotted path string.

    :arg resource_type: the resource type name (required). i.e Organization
    :arg cache: (default True) the flag which indicates should query fresh or
    serve from cache if available.
    :arg fhir_release: FHIR Release (version) name.
    i.e FHIR_VERSION.STU3, FHIR_VERSION.R4
    :return dotted full string path. i.e fhir.resources.organization.Organization

    Example::

        >>> from guillotina_fhirfield.helpers import search_fhir_resource_cls
        >>> from zope.interface import Invalid
        >>> dotted_path = search_fhir_resource_cls('Patient')
        >>> 'fhir.resources.patient.Patient' == dotted_path
        True
        >>> dotted_path = search_fhir_resource_cls('FakeResource')
        >>> dotted_path is None
        True
    """
    cache_path = FHIR_RESOURCE_CLASS_CACHE[fhir_release]

    if resource_type in cache_path and cache:
        return cache_path[resource_type]

    # Trying to get from entire modules
    prime_module = ["fhir", "resources"]
    if FHIR_VERSION.DEFAULT != fhir_release:
        prime_module.append(fhir_release)

    prime_module_level = len(prime_module)
    prime_module = '.'.join(prime_module)

    prime_module = import_module(prime_module)

    for importer, module_name, ispkg in pkgutil.walk_packages(
        prime_module.__path__, prime_module.__name__ + ".", onerror=lambda x: None
    ):
        if ispkg or (prime_module_level + 1) < len(module_name.split(".")):
            continue

        module_obj = import_module(module_name)

        for klass_name, klass in inspect.getmembers(module_obj, inspect.isclass):

            if klass_name == resource_type:
                cache_path[resource_type] = f"{module_name}.{resource_type}"
                return cache_path[resource_type]

    return None
