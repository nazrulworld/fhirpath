# _*_ coding: utf-8 _*_
import inspect
import os
import pkgutil
import re
import sys
from importlib import import_module
from typing import Union

import pkg_resources
from zope.interface import implementer

from fhirpath.thirdparty import Proxy

from .enums import FHIR_VERSION
from .interfaces import IPathInfoContext
from .storage import FHIR_RESOURCE_CLASS_STORAGE
from .storage import PATH_INFO_STORAGE
from .types import PrimitiveDataTypes


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

NoneType = type(None)


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
    storage = FHIR_RESOURCE_CLASS_STORAGE.get(fhir_release.value)

    if storage.exists(resource_type) and cache:
        return storage.get(resource_type)

    # Trying to get from entire modules
    prime_module = ["fhir", "resources"]
    if FHIR_VERSION.DEFAULT != fhir_release:
        prime_module.append(fhir_release.value)

    prime_module_level = len(prime_module)
    prime_module = ".".join(prime_module)

    prime_module = import_module(prime_module)

    for importer, module_name, ispkg in pkgutil.walk_packages(
        prime_module.__path__, prime_module.__name__ + ".", onerror=lambda x: None
    ):
        if ispkg or (prime_module_level + 1) < len(module_name.split(".")):
            continue

        module_obj = import_module(module_name)

        for klass_name, klass in inspect.getmembers(module_obj, inspect.isclass):

            if klass_name == resource_type:
                storage.insert(resource_type, f"{module_name}.{resource_type}")
                return storage.get(resource_type)

    return None


CONTAINS_PY_PACKAGE = re.compile(r"^\$\{(?P<package_name>[0-9a-z._]+)\}", re.IGNORECASE)


def expand_path(path_: str):
    """Path normalizer
    Supports:
    1. Home Path expander
    2. Package path discovery"""

    if path_.startswith("~"):
        real_path = os.path.expanduser(path_)

    elif CONTAINS_PY_PACKAGE.match(path_):
        match = CONTAINS_PY_PACKAGE.match(path_)
        replacement = match.group(0)
        package_name = match.group("package_name")

        try:
            real_path = path_.replace(
                replacement, pkg_resources.get_distribution(package_name).location
            )
        except pkg_resources.DistributionNotFound:
            msg = "Invalid package `{0}`! as provided in {1}".format(
                package_name, path_
            )
            reraise(LookupError, msg)

    else:
        real_path = path_

    if real_path.endswith(os.sep):
        real_path = real_path[: -len(os.sep)]

    return real_path


def proxy(obj):
    """Making proxy of any object"""
    try:
        return getattr(obj, "__proxy__")()
    except AttributeError:
        # trying to make ourself
        p_obj = Proxy()
        p_obj.initialize(obj)
        return p_obj


def unwrap_proxy(proxy_obj):
    """ """
    assert isinstance(proxy_obj, Proxy)
    return proxy_obj.obj


class EmptyPathInfoContext:
    """Empty PathInfoContext for start(*) path!"""

    def __init__(self):
        """ """
        self._parent = None
        self._children = None
        self._path = "*"

        self.fhir_release = None
        self.prop_name = None
        self.prop_original = None
        self.type_name = None
        self.type_class = None
        self.optional = None
        self.multiple = None


EMPTY_PATH_INFO_CONTEXT = EmptyPathInfoContext()


@implementer(IPathInfoContext)
class PathInfoContext:
    """ """

    def __init__(
        self,
        path,
        fhir_release,
        prop_name,
        prop_original,
        type_name,
        type_class,
        optional,
        multiple,
    ):
        """ """
        self._parent = None
        self._children = list()
        self._path = path

        self.fhir_release = fhir_release
        self.prop_name = prop_name
        self.prop_original = prop_original
        self.type_name = type_name
        self.type_class = type_class
        self.optional = optional
        self.multiple = multiple

    @classmethod
    def context_from_path(cls, pathname: str, fhir_release: FHIR_VERSION):
        """ """
        if pathname == "*":
            return EMPTY_PATH_INFO_CONTEXT

        storage = PATH_INFO_STORAGE.get(fhir_release.value)

        if storage.exists(pathname):
            # trying from cache!
            return storage.get(pathname)

        parts = pathname.split(".")
        model = lookup_fhir_class_path(parts[0], fhir_release=fhir_release)
        model = import_string(model)
        new_path = parts[0]
        context = None

        for index, part in enumerate(parts[1:], 1):

            new_path = "{0}.{1}".format(new_path, part)
            if storage.exists(new_path):
                context = storage.get(new_path)
                if context.type_name in PrimitiveDataTypes:
                    if (index + 1) < len(parts):
                        raise ValueError("Invalid path {0}".format(pathname))
                    break
                else:
                    model = context.type_class
                    continue

            for (
                name,
                jsname,
                typ,
                typ_name,
                is_list,
                of_many,
                not_optional,
            ) in model().elementProperties():

                if part != jsname:
                    continue
                if typ_name in PrimitiveDataTypes:
                    type_class = PrimitiveDataTypes.get(typ_name)
                    is_primitive = True
                else:
                    type_class = typ
                    is_primitive = False

                context = cls(
                    new_path,
                    fhir_release=fhir_release,
                    prop_name=name,
                    prop_original=jsname,
                    type_name=typ_name,
                    type_class=type_class,
                    optional=(not not_optional),
                    multiple=is_list,
                )
                if index > 1:
                    context.parent = ".".join(new_path.split(".")[:-1])
                    # Get Property: should return parent Context obj instead
                    # of just string
                    parent_context = context.parent
                    parent_context.add_child(new_path)

                storage.insert(new_path, context)
                if not is_primitive:
                    model = type_class
                else:
                    if (index + 1) < len(parts):
                        raise ValueError("Invalid path {0}".format(pathname))
                    break
            # important! even context is None, that means not valid path (part)
            if context is None:
                break
        return context

    def __proxy__(self):
        """ """
        return PathInfoContextProxy(self)

    def _set_parent(self, dotted_path: str):
        """ """
        self._parent = dotted_path

    def _get_parent(self):
        """ """
        return PathInfoContext.context_from_path(self._parent, self.fhir_release)

    parent = property(_get_parent, _set_parent)

    def _get_children(self):
        """ """
        return [
            PathInfoContext.context_from_path(child, self.fhir_release)
            for child in self._children
        ]

    def _set_children(self, paths):
        """ """
        if isinstance(paths, str):
            paths = [paths]
        self._children = paths

    children = property(_get_children, _set_children)

    def is_root(self):
        """ """
        return self._parent is None

    def add_child(self, path):
        """ """
        if path not in self._children:
            self._children.append(path)

    def __repr__(self):
        """ """
        return "<{0}.{1}('{2}')>".format(
            self.__class__.__module__, self.__class__.__name__, self._path
        )

    def __str__(self):
        """ """
        return str(self._path)


class PathInfoContextProxy(Proxy):
    """ """

    def __init__(self, context: PathInfoContext):
        """ """
        super(PathInfoContextProxy, self).__init__()
        self.initialize(context)
