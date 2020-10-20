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
from inspect import signature
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Match,
    Optional,
    Pattern,
    Text,
    Type,
    Union,
    cast,
)

import orjson
import pkg_resources
from pydantic.json import pydantic_encoder
from pydantic.validators import bool_validator
from yarl import URL
from zope.interface import implementer

from fhirpath.thirdparty import Proxy

from .enums import FHIR_VERSION
from .interfaces import IPathInfoContext
from .storage import FHIR_RESOURCE_CLASS_STORAGE, PATH_INFO_STORAGE
from .types import PrimitiveDataTypes

if TYPE_CHECKING:
    from fhir.resources.fhirabstractmodel import FHIRAbstractModel  # noqa: F401
    from fhir.resources.fhirtypes import (  # noqa: F401
        AbstractBaseType,
        AbstractType,
        Primitive,
    )
    from pydantic.fields import ModelField  # noqa: F401
    from pydantic.main import BaseConfig  # noqa: F401


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


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


def force_str(value: Any, allow_non_str: bool = True) -> Text:
    """ """
    if isinstance(value, bytes):
        return value.decode("utf8", "strict")

    if not isinstance(value, str) and allow_non_str:
        value = str(value)
    return value


def force_bytes(
    string: Text, encoding: Text = "utf8", errors: Text = "strict"
) -> bytes:

    if isinstance(string, bytes):
        if encoding == "utf8":
            return string
        else:
            return string.decode("utf8", errors).encode(encoding, errors)

    if not isinstance(string, str):
        string = str(string)

    return string.encode(encoding, errors)


def import_string(dotted_path: Text) -> type:
    """Shameless hack from django utils, please don't mind!"""
    module_path: Text
    class_name: Text
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except (ValueError, AttributeError):
        msg = f"{dotted_path} doesnt look like a module path"
        return reraise(ImportError, msg)

    module: ModuleType = import_module(module_path)
    cls: type
    try:
        cls = getattr(module, class_name)
    except AttributeError:
        msg = f'Module "{module_path}" does not define a "{class_name}" attribute/class'
        return reraise(ImportError, msg)
    return cls


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
    resource_type: Text,
    cache: bool = True,
    fhir_release: FHIR_VERSION = FHIR_VERSION.DEFAULT,
) -> Optional[Text]:  # noqa: E999
    """This function finds FHIR resource model class (from fhir.resources) and
    return dotted path string.

    :arg resource_type: the resource type name (required). i.e Organization

    :arg cache: (default True) the flag which indicates should query fresh or
        serve from cache if available.

    :arg fhir_release: FHIR Release (version) name.
        i.e FHIR_VERSION.STU3, FHIR_VERSION.R4

    :return dotted full string path. i.e fhir.resources.organization.Organization

    Example::

        >>> from fhirpath.utils import lookup_fhir_class_path
        >>> from zope.interface import Invalid
        >>> dotted_path = lookup_fhir_class_path('Patient')
        >>> 'fhir.resources.patient.Patient' == dotted_path
        True
        >>> dotted_path = lookup_fhir_class_path('FakeResource')
        >>> dotted_path is None
        True
    """
    fhir_release = FHIR_VERSION.normalize(fhir_release)

    storage = FHIR_RESOURCE_CLASS_STORAGE.get(fhir_release.name)

    if storage.exists(resource_type) and cache:
        return storage.get(resource_type)

    # Trying to get from entire modules
    prime_module: List[Text] = ["fhir", "resources"]
    if FHIR_VERSION["DEFAULT"].value != fhir_release.name:
        prime_module.append(fhir_release.name)

    prime_module_level = len(prime_module)
    prime_module_path: Text = ".".join(prime_module)

    prime_module_type: ModuleType = import_module(prime_module_path)

    for _importer, module_name, ispkg in pkgutil.walk_packages(
        prime_module_type.__path__,  # type: ignore
        prime_module_type.__name__ + ".",
        onerror=lambda x: None,
    ):
        if ispkg or (prime_module_level + 1) < len(module_name.split(".")):
            continue

        module_type: ModuleType = import_module(module_name)

        for klass_name, _klass in inspect.getmembers(module_type, inspect.isclass):

            if klass_name == resource_type:
                storage.insert(resource_type, f"{module_name}.{resource_type}")
                return storage.get(resource_type)
    return None


def lookup_fhir_class(
    resource_type: Text, fhir_release: FHIR_VERSION = FHIR_VERSION.DEFAULT
) -> Type["FHIRAbstractModel"]:  # noqa: E999
    factory_paths: List[str] = ["fhir", "resources"]
    if (
        FHIR_VERSION["DEFAULT"].value != fhir_release.name
        and fhir_release != FHIR_VERSION.DEFAULT
    ):
        factory_paths.append(fhir_release.name)
    factory_paths.append("get_fhir_model_class")

    factory: type = import_string(".".join(factory_paths))
    try:
        klass = factory(resource_type)
    except KeyError:
        raise LookupError(f"{resource_type} is not a valid FHIR class")
    return klass


CONTAINS_PY_PACKAGE: Pattern = re.compile(
    r"^\${(?P<package_name>[0-9a-z._]+)\}", re.IGNORECASE
)


def expand_path(path_: Text) -> Text:
    """Path normalizer
    Supports:
    1. Home Path expander
    2. Package path discovery"""

    pkg_matched: Optional[Match[Text]] = CONTAINS_PY_PACKAGE.match(path_)
    if path_.startswith("~"):
        real_path = os.path.expanduser(path_)

    elif pkg_matched is not None:
        replacement = pkg_matched.group(0)
        package_name = pkg_matched.group("package_name")

        try:
            real_path = path_.replace(
                replacement, pkg_resources.get_distribution(package_name).location
            )
        except pkg_resources.DistributionNotFound:
            msg = "Invalid package `{0}`! as provided in {1}".format(
                package_name, path_
            )
            return reraise(LookupError, msg)

    else:
        real_path = path_

    if real_path.endswith(os.sep):
        real_path = real_path[: -len(os.sep)]

    return real_path


def proxy(obj):
    """Making proxy of any object"""
    try:
        return obj.__proxy__()
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
        self.type_is_primitive = None


EMPTY_PATH_INFO_CONTEXT = EmptyPathInfoContext()


@implementer(IPathInfoContext)
class PathInfoContext:
    """ """

    def __init__(
        self,
        path: str,
        fhir_release: FHIR_VERSION,
        prop_name: str,
        prop_original: str,
        type_name: str,
        type_class: Union[bool, "AbstractBaseType", "AbstractType", "Primitive"],
        type_field: "ModelField",
        type_model_config: Type["BaseConfig"],
        optional: bool,
        multiple: bool,
        type_is_primitive: bool,
        resource_type: str,
    ):
        """ """
        self._parent: Optional[str] = None
        self._children: List[str] = list()
        self._path: str = path

        self.fhir_release: FHIR_VERSION = fhir_release
        self.prop_name: str = prop_name
        self.prop_original: str = prop_original
        self.type_name: str = type_name
        self.type_class: Union[
            bool, "AbstractBaseType", "AbstractType", "Primitive"
        ] = type_class
        self.type_field: "ModelField" = type_field
        self.type_model_config: Type["BaseConfig"] = type_model_config
        self.optional: bool = optional
        self.multiple: bool = multiple
        self.type_is_primitive: bool = type_is_primitive
        self.resource_type: str = resource_type

    @classmethod
    def context_from_path(
        cls, pathname: Text, fhir_release: FHIR_VERSION
    ) -> Union["PathInfoContext", "EmptyPathInfoContext"]:
        """ """
        if pathname == "*":
            return EMPTY_PATH_INFO_CONTEXT

        fhir_release = FHIR_VERSION.normalize(fhir_release)

        storage = PATH_INFO_STORAGE.get(fhir_release.name)

        if storage.exists(pathname):
            # trying from cache!
            return storage.get(pathname)

        parts = pathname.split(".")
        resource_type = parts[0]
        model_path = lookup_fhir_class_path(resource_type, fhir_release=fhir_release)
        model_class: Type["FHIRAbstractModel"] = cast(
            Type["FHIRAbstractModel"], import_string(cast(Text, model_path))
        )
        new_path: Text = parts[0]
        context: Optional["PathInfoContext"] = None

        for index, part in enumerate(parts[1:], 1):

            new_path = "{0}.{1}".format(new_path, part)
            if storage.exists(new_path):
                context = storage.get(new_path)
                if TYPE_CHECKING:
                    assert context
                if context.type_name in PrimitiveDataTypes:
                    if (index + 1) < len(parts):
                        raise ValueError("Invalid path {0}".format(pathname))
                    break
                else:
                    klass = context.type_class
                    model_class = lookup_fhir_class(
                        klass.__resource_type__,  # type: ignore
                        FHIR_VERSION[klass.__fhir_release__],  # type: ignore
                    )
                    continue

            for field in model_class.element_properties():

                if part != field.alias:
                    continue
                type_model_config = model_class.__config__
                multiple = str(field.outer_type_)[:12] == "typing.List["
                if getattr(field.type_, "__resource_type__", None):
                    # AbstractModelType
                    model_class = lookup_fhir_class(
                        field.type_.__resource_type__,
                        FHIR_VERSION[field.type_.__fhir_release__],
                    )
                    type_name = field.type_.__resource_type__
                    is_primitive = False
                else:
                    is_primitive = True
                    # Primitive
                    type_name = getattr(field.type_, "__visit_name__", None)
                    if type_name is None and field.type_ == bool:
                        type_name = "boolean"
                    if type_name is None:
                        raise NotImplementedError

                context = cls(
                    new_path,
                    fhir_release=fhir_release,
                    prop_name=field.name,
                    prop_original=field.alias,
                    type_name=type_name,
                    type_class=field.type_,
                    type_field=field,
                    type_model_config=type_model_config,
                    optional=(not field.required),
                    multiple=multiple,
                    type_is_primitive=is_primitive,
                    resource_type=resource_type,
                )
                if index > 1:
                    context.parent = ".".join(new_path.split(".")[:-1])
                    # Get Property: should return parent Context obj instead
                    # of just string
                    parent_context = context.parent
                    parent_context.add_child(new_path)  # type: ignore

                storage.insert(new_path, context)

                if is_primitive:
                    if (index + 1) < len(parts):
                        raise ValueError("Invalid path {0}".format(pathname))
                    break
            # important! even context is None, that means not valid path (part)
            if context is None:
                break
        if TYPE_CHECKING:
            assert context
        return context

    def __proxy__(self):
        """ """
        return PathInfoContextProxy(self)

    def _set_parent(self, dotted_path: str):
        """ """
        self._parent = dotted_path

    def _get_parent(self) -> "PathInfoContext":
        """ """
        assert self._parent
        parent = PathInfoContext.context_from_path(self._parent, self.fhir_release)
        if TYPE_CHECKING:
            assert isinstance(parent, PathInfoContext)
        return parent

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

    def validate_value(self, value):
        """``pydantic`` way to validate value"""
        if self.type_class == bool:
            return bool_validator(value)
        for validator in self.type_class.__get_validators__():
            sig = signature(validator)
            args = list(sig.parameters.keys())
            if len(args) == 1:
                value = validator(value)
            elif len(args) == 2:
                value = validator(value, self.type_field)
            elif len(args) == 3:
                value = validator(value, self.type_field, self.type_model_config)
            else:
                raise NotImplementedError
        return value


class PathInfoContextProxy(Proxy):
    """ """

    def __init__(self, context: PathInfoContext):
        """ """
        super(PathInfoContextProxy, self).__init__()
        self.initialize(context)


class BundleWrapper:
    """ """

    def __init__(
        self, engine, result, includes: List, url: URL, bundle_type="searchset"
    ):
        """ """
        self.fhir_version = engine.fhir_release
        self.bundle_model = lookup_fhir_class("Bundle", fhir_release=self.fhir_version)
        self.data: Dict[str, Any] = dict()
        self.data["id"] = str(uuid.uuid4())

        self.data["meta"] = {"lastUpdated": datetime.datetime.utcnow()}

        self.data["type"] = bundle_type
        # our pagination is based main query result.
        # fixme: still issue for _has chaining
        self.data["total"] = result.header.total

        # attach main results
        self.attach_entry(result, "match")

        # attach included results
        for _include in includes:
            self.attach_entry(_include, "include")

        self.attach_links(url, len(result.body))

    def attach_entry(self, result, mode="match"):
        """ """
        if "entry" not in self.data:
            self.data["entry"] = list()

        for row in result.body:
            resource = row[0]
            if isinstance(resource, dict):
                resource_id = resource["id"]
                resource_type = resource["resourceType"]
            else:
                resource_id = resource.id
                resource_type = resource.resource_type
            # entry = BundleEntry
            entry = dict()
            entry["fullUrl"] = "{0}/{1}".format(resource_type, resource_id)
            entry["resource"] = resource
            # search = BundleEntrySearch
            search = {"mode": mode}
            entry["search"] = search

            self.data["entry"].append(entry)

    def attach_links(self, url, entries_count):
        """ """
        container = list()

        _max_count = int(url.query.get("_count", 100))
        _total_results = self.data["total"]
        _current_offset = int(url.query.get("search-offset", 0))
        url_params = {}

        container.append(self.make_link("self", url))

        # let's pagination here
        if _total_results > _max_count:
            # Yes pagination is required!
            url_params["_count"] = _max_count
            url_params["search-id"] = self.data["id"]

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

        self.data["link"] = container

    def make_link(self, relation, url, params=None):
        """ """
        params = params or {}
        # link = BundleLink
        link = {"relation": relation}
        # fix: params
        existing_params = url.query.copy()
        for key in params:
            existing_params[key] = params[key]

        new_url = url.with_query(existing_params)
        link["url"] = str(new_url)

        return link

    def __call__(self, as_json=False):
        """ """
        if as_json:
            # if as_json is True, return the bundle as python dict
            # instead of building a pydantic.BaseModel
            # important!
            self.data["resourceType"] = self.bundle_model.get_resource_type()
            return self.data
        return self.bundle_model.parse_obj(self.data)

    def json(self):
        """ """
        return self.__call__().json()


def json_dumps(
    value: Union[List[Dict[str, Any]], Dict[str, Any]],
    *,
    default: Callable = None,
    option: int = 0,
    indent: int = None,
    sort_keys: bool = None,
    return_bytes: bool = False,
) -> Union[str, bytes]:
    """Special helper function to serialize to json str, powered by ``orjson``"""
    if default is None:
        default = pydantic_encoder

    params: Any = {"default": default}
    option_ = option
    if option_ == 0:
        if indent is not None:
            # only indent 2 is accepted
            option_ |= orjson.OPT_INDENT_2
        if sort_keys is not None and sort_keys:
            option_ |= orjson.OPT_SORT_KEYS

    if option_ > 0:
        params.update({"option": option_})

    v = orjson.dumps(value, **params)
    if return_bytes is False:
        return force_str(v)
    return v


def json_loads(
    value: Union[bytes, bytearray, str]
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """bytes, bytearray, and str input are accepted.
    If the input exists as bytes (was read directly from a source),
    it is recommended to pass bytes. This has lower memory usage and lower latency.

    The input must be valid UTF-8."""

    return orjson.loads(value)
