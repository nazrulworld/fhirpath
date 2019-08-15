# _*_ coding: utf-8 _*_
import datetime
import inspect
import math
import os
import pkgutil
import re
import sys
import uuid
from importlib import import_module
from typing import Union

import pkg_resources
from yarl import URL
from zope.interface import implementer

from fhirpath.thirdparty import Proxy

from .enums import FHIR_VERSION
from .interfaces import IModel
from .interfaces import IPathInfoContext
from .navigator import PathNavigator
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
        msg = f"{dotted_path} doesn't look like a module path"
        return reraise(ImportError, msg)

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError:
        msg = f'Module "{module_path}" does not define a "{class_name}" attribute/class'
        return reraise(ImportError, msg)


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


def lookup_fhir_class(
    resource_type: str, fhir_release: FHIR_VERSION = FHIR_VERSION.DEFAULT
):  # noqa: E999
    klass_path = lookup_fhir_class_path(resource_type, True, fhir_release)
    klass = import_string(klass_path)
    return klass


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
    def create(resource_type: str, fhir_version: FHIR_VERSION = FHIR_VERSION.DEFAULT):
        """ """
        klass = import_string(
            lookup_fhir_class_path(resource_type, fhir_release=fhir_version)
        )
        # xxx: should be cache?
        model = ModelFactory(f"{klass.__name__}Model", (klass, PathNavigator), {})

        return model


class BundleWrapper:
    """ """

    def __init__(self, engine, result, url: URL, bundle_type="searchset"):
        """ """
        self.fhir_version = engine.fhir_release
        self.bundle = lookup_fhir_class("Bundle", fhir_release=self.fhir_version)()
        self.bundle.id = str(uuid.uuid4())

        self.bundle.meta = lookup_fhir_class("Meta", fhir_release=self.fhir_version)()

        fhir_dt = lookup_fhir_class("FHIRDate", fhir_release=self.fhir_version)()
        fhir_dt.date = datetime.datetime.now()
        self.bundle.meta.lastModified = fhir_dt

        self.bundle.type = bundle_type
        self.bundle.total = result.header.total

        self.attach_entry(result, "match")

        self.attach_links(url, len(result.body))

    def attach_entry(self, result, mode="match"):
        """ """
        if not self.bundle.entry:
            self.bundle.entry = list()

        for entry in result.body:
            resource = lookup_fhir_class(
                entry["resourceType"], fhir_release=self.fhir_version
            )(entry)

            item = lookup_fhir_class("BundleEntry", fhir_release=self.fhir_version)()
            item.fullUrl = "{0}/{1}".format(resource.resource_type, resource.id)
            item.resource = resource

            item.search = lookup_fhir_class(
                "BundleEntrySearch", fhir_release=self.fhir_version
            )()
            item.search.mode = mode

            self.bundle.entry.append(item)

    def attach_links(self, url, entries_count):
        """ """
        container = list()

        _max_count = int(url.query.get("_count", 100))
        _total_results = self.bundle.total
        _current_offset = int(url.query.get("search-offset", 0))
        url_params = {}

        container.append(self.make_link("self", url))

        # let's pagitionation here
        if _total_results > _max_count:
            # Yes pagination is required!
            url_params["_count"] = _max_count
            url_params["search-id"] = self.bundle.id

            # first page
            if _current_offset != 0:
                url_params["search-offset"] = 0
                container.append(self.make_link("first", url, url_params))
            # Previous Page
            if _current_offset > 0:
                url_params["search-offset"] = int(_current_offset - _max_count)
                container.append(self.make_link("previous", url, url_params))

            # Next Page
            if _current_offset < int(
                math.floor(_total_results / _max_count) * _max_count
            ):
                url_params["search-offset"] = int(_current_offset + _max_count)
                container.append(self.make_link("next", url, url_params))

            # last page
            last_offset = int(math.floor(_total_results / _max_count) * _max_count)
            if (_total_results % last_offset) == 0:
                last_offset -= _max_count

            if _current_offset < last_offset and last_offset > 0:

                url_params["search-offset"] = last_offset
                container.append(self.make_link("last", url, url_params))

        self.bundle.link = container

    def make_link(self, relation, url, params={}):
        """ """
        item = lookup_fhir_class("BundleLink", fhir_release=self.fhir_version)()
        item.relation = relation
        # fix: params
        existing_params = url.query.copy()
        for key in params:
            existing_params[key] = params[key]

        new_url = url.with_query(existing_params)
        item.url = str(new_url)

        return item

    def __call__(self):
        """ """
        # Validation purpose
        self.as_json()
        return self.bundle

    def as_json(self):
        """ """
        return self.bundle.as_json()
