# _*_ coding: utf-8 _*_
import datetime
import math
import os
import re
import sys
import time
import types
import typing
import uuid
from importlib import import_module
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Match,
    Optional,
    Pattern,
    Text,
    Type,
    Union,
)

import pkg_resources
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from yarl import URL
from zope.interface import implementer

from fhirpath.thirdparty import Proxy

from ..core.model import class_fields
from ..enums import FHIR_VERSION
from ..utils import (  # noqa: F401  (re-exported, historically defined here)
    lookup_all_fhir_domain_resource_classes,
    lookup_fhir_class,
    lookup_fhir_class_path,
)
from .interfaces import IPathInfoContext
from ..json import json_dumps, json_loads  # noqa: F401
from .storage import PATH_INFO_STORAGE

if TYPE_CHECKING:
    from fhir_core.fhirabstractmodel import FHIRAbstractModel


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

LOCAL_TIMEZONE: Optional[datetime.timezone] = None


def fallback_callable(*args, **kwargs):
    """Always return None"""
    return None


def _reraise(tp, value, tb=None):
    if value is None:
        value = tp
    if value.__traceback__ is not tb:
        raise value.with_traceback(tb)
    raise value


def reraise(klass, msg=None, callback=None, **kw):
    """Reraise custom exception class"""
    if not issubclass(klass, Exception):
        raise RuntimeError(f"Class ``{klass}`` must be derived from Exception class.")
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


CONTAINS_PY_PACKAGE: Pattern = re.compile(
    r"^\${(?P<package_name>[0-9a-z._]+)}", re.IGNORECASE
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


class FHIRTypeInfo:
    """Type of an element path, derived from the ``fhir.resources`` (pydantic 2) models.

    Keeps the protocol of the fhir.resources 6 ``fhirtypes`` classes the search code
    relies on: ``is_primitive()``, ``fhir_type_name()``, ``__resource_type__`` and
    ``__fhir_release__``. Values are validated with a pydantic ``TypeAdapter`` built
    from the field annotation.
    """

    __slots__ = ("name", "model_class", "annotation", "fhir_release", "_adapter")

    def __init__(
        self,
        name: str,
        model_class: Optional[Type["FHIRAbstractModel"]],
        annotation: Any,
        fhir_release: FHIR_VERSION,
    ):
        self.name = name
        self.model_class = model_class
        self.annotation = annotation
        self.fhir_release = fhir_release
        self._adapter: Optional[TypeAdapter] = None

    def is_primitive(self) -> bool:
        return self.model_class is None

    def fhir_type_name(self) -> str:
        return self.name

    @property
    def __resource_type__(self) -> str:
        return self.name

    @property
    def __fhir_release__(self) -> str:
        return self.fhir_release.name

    @property
    def __visit_name__(self) -> str:
        return self.name

    def validate(self, value: Any) -> Any:
        """Validate/convert ``value`` the way the model field would.

        Date/time *search values* are parsed leniently into ``date``/``datetime``/
        ``time`` objects: FHIR search allows ``2019-07-17T19:32:59`` without an
        offset, which the strict resource datatypes reject.
        """
        if isinstance(value, str) and self.name in _TEMPORAL_ADAPTERS:
            parsed = _parse_search_temporal(self.name, value)
            if parsed is not None:
                return parsed
        if self._adapter is None:
            self._adapter = TypeAdapter(self.annotation)
        return self._adapter.validate_python(value)

    def __eq__(self, other):
        if isinstance(other, FHIRTypeInfo):
            return (self.name, self.fhir_release) == (other.name, other.fhir_release)
        return NotImplemented

    def __hash__(self):
        return hash((self.name, self.fhir_release))

    def __repr__(self):
        return "<FHIRTypeInfo %s (%s)>" % (self.name, self.fhir_release.name)


_TEMPORAL_ADAPTERS = {
    "date": TypeAdapter(datetime.date),
    "dateTime": TypeAdapter(datetime.datetime),
    "instant": TypeAdapter(datetime.datetime),
    "time": TypeAdapter(datetime.time),
}
_FULL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_search_temporal(type_name: str, value: str) -> Any:
    """Full date / date-time / time search value -> Python object, else ``None``.

    Partial dates (``2010``, ``2010-05``) return ``None`` and go through the
    regular (model) validation, which keeps them as strings.
    """
    try:
        if type_name == "time":
            return _TEMPORAL_ADAPTERS["time"].validate_python(value)
        if "T" in value:
            return _TEMPORAL_ADAPTERS["dateTime"].validate_python(value)
        if _FULL_DATE.match(value):
            return _TEMPORAL_ADAPTERS["date"].validate_python(value)
    except PydanticValidationError:
        return None
    return None


def _field_annotation(model_class: Type["FHIRAbstractModel"], attr: str) -> Any:
    """Item annotation of a model field (Optional[...] and List[...] removed)."""
    annotation = model_class.model_fields[attr].annotation
    while True:
        origin = typing.get_origin(annotation)
        if origin is Union or origin is types.UnionType:
            args = [a for a in typing.get_args(annotation) if a is not type(None)]
            annotation = args[0] if len(args) == 1 else Union[tuple(args)]
            if len(args) != 1:
                return annotation
            continue
        if origin in (list, List):
            annotation = typing.get_args(annotation)[0]
            continue
        return annotation


@implementer(IPathInfoContext)
class PathInfoContext:
    """Type information of a FHIR element path, e.g. ``Patient.name.given``."""

    def __init__(
        self,
        path: str,
        fhir_release: FHIR_VERSION,
        prop_name: str,
        prop_original: str,
        type_name: str,
        type_class: FHIRTypeInfo,
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
        self.type_class: FHIRTypeInfo = type_class
        self.optional: bool = optional
        self.multiple: bool = multiple
        self.type_is_primitive: bool = type_is_primitive
        self.resource_type: str = resource_type

    @classmethod
    def context_from_path(
        cls, pathname: Text, fhir_release: FHIR_VERSION
    ) -> Optional[Union["PathInfoContext", "EmptyPathInfoContext"]]:
        """Context of ``pathname`` (``None`` when the path is not valid)."""
        if pathname == "*":
            return EMPTY_PATH_INFO_CONTEXT

        fhir_release = FHIR_VERSION.normalize(fhir_release)

        storage = PATH_INFO_STORAGE.get(fhir_release.name)

        if storage.exists(pathname):
            # trying from cache!
            return storage.get(pathname)

        parts = pathname.split(".")
        resource_type = parts[0]
        try:
            model_class: Optional[Type["FHIRAbstractModel"]] = lookup_fhir_class(
                resource_type, fhir_release
            )
        except LookupError:
            return None
        new_path: Text = parts[0]
        context: Optional["PathInfoContext"] = None

        for index, part in enumerate(parts[1:], 1):
            new_path = "{0}.{1}".format(new_path, part)
            if model_class is None:
                # a primitive cannot have children
                raise ValueError("Invalid path {0}".format(pathname))

            if storage.exists(new_path):
                context = storage.get(new_path)
                model_class = context.type_class.model_class
                continue

            meta = class_fields(model_class)[0].get(part)
            if meta is None:
                # important! not a valid path (part)
                return None

            type_name = meta.type_name or "Resource"
            child_class = meta.klass
            if child_class is None and meta.type_name is None:
                child_class = lookup_fhir_class("Resource", fhir_release)
            is_primitive = child_class is None
            info = model_class.model_fields[meta.attr]
            context = cls(
                new_path,
                fhir_release=fhir_release,
                prop_name=meta.attr,
                prop_original=meta.json_name,
                type_name=type_name,
                type_class=FHIRTypeInfo(
                    type_name,
                    child_class,
                    _field_annotation(model_class, meta.attr),
                    fhir_release,
                ),
                optional=not info.is_required(),
                multiple=meta.is_list,
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
            model_class = child_class
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

    def get_real_type_class(self) -> FHIRTypeInfo:
        """ """
        return self.type_class

    def __repr__(self):
        """ """
        return "<{0}.{1}('{2}')>".format(
            self.__class__.__module__, self.__class__.__name__, self._path
        )

    def __str__(self):
        """ """
        return str(self._path)

    def validate_value(self, value):
        """Validate a search value against the element type (pydantic 2)."""
        try:
            return self.type_class.validate(value)
        except PydanticValidationError as exc:
            raise ValueError(
                "Invalid value {0!r} for {1} ({2}): {3}".format(
                    value, self._path, self.type_name, exc.errors()[0].get("msg")
                )
            ) from exc


class PathInfoContextProxy(Proxy):
    """ """

    def __init__(self, context: PathInfoContext):
        """ """
        super(PathInfoContextProxy, self).__init__()
        self.initialize(context)


class BundleWrapper:
    """ """

    FHIR_REST_SERVER_PATH_PATTERN: Optional[Pattern] = None

    def __init__(
        self,
        engine,
        result,
        includes: List,
        url: URL,
        bundle_type="searchset",
        *,
        base_url: URL = None,
        init_data: Dict[str, Any] = None,
    ):
        """ """
        self.fhir_version = engine.fhir_release
        self.bundle_model = lookup_fhir_class("Bundle", fhir_release=self.fhir_version)
        self.base_url: URL = base_url or BundleWrapper.calculate_fhir_base_url(url)
        if init_data:
            self.data = init_data
        else:
            self.data = BundleWrapper.init_data()

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

    @classmethod
    def fhir_rest_server_path_pattern(cls):
        """ """
        if cls.FHIR_REST_SERVER_PATH_PATTERN is None:
            all_resource_domain_types = set()
            for release in (FHIR_VERSION.R5, FHIR_VERSION.R4B, FHIR_VERSION.STU3):
                all_resource_domain_types.update(
                    lookup_all_fhir_domain_resource_classes(release).keys()
                )
            all_resources = "|".join(all_resource_domain_types)

            pattern = re.compile(
                r"(?:(/(?P<resource_name>" + all_resources + r")"
                r"(?:"
                r"(?P<search2>/_search)|"
                r"(?P<resource_id>/[A-Za-z0-9\-.]{1,64})(?P<history>/_history)?"
                r")?"
                r")|(?P<search1>/_search))?"
                r"(?P<graphql>/\$graphql)?$"
            )
            cls.FHIR_REST_SERVER_PATH_PATTERN = pattern

        return cls.FHIR_REST_SERVER_PATH_PATTERN

    @staticmethod
    def calculate_fhir_base_url(url: URL) -> URL:
        """https://www.hl7.org/fhir/Bundle.html
        Section: 2.36.4 Resource URL & Uniqueness rules in a bundle.
        Section: 2.36.4.1 Resolving references in Bundles.
        """
        _url = url
        raw_path = url.raw_path
        if len(raw_path) > 1 and raw_path.endswith("/"):
            raw_path = raw_path[:-1]

        matches = BundleWrapper.fhir_rest_server_path_pattern().search(raw_path)
        group_dict = {}
        if matches:
            group_dict = matches.groupdict()
        if group_dict.get("resource_name"):
            _url = _url.parent
            if group_dict.get("resource_id"):
                _url = _url.parent
                if group_dict.get("history"):
                    _url = _url.parent
            elif group_dict.get("search2"):
                _url = _url.parent
        elif group_dict.get("search1"):
            _url = _url.parent

        if group_dict.get("graphql"):
            _url = _url.parent
        return _url

    @staticmethod
    def init_data() -> Dict[str, Any]:
        """Initialized Bundle data"""
        data = {"id": str(uuid.uuid4()), "meta": {"lastUpdated": timestamp_utc()}}
        return data

    def attach_entry(self, result, mode="match"):
        """ """
        if "entry" not in self.data:
            self.data["entry"] = list()

        for row in result.body:
            resource = row[0]
            if isinstance(resource, dict):
                resource_id = resource["id"]
                resource_type = resource["resourceType"]
            elif getattr(resource.__class__, "get_resource_type", fallback_callable)():
                resource_id = resource.id
                resource_type = resource.resource_type
            else:
                raise NotImplementedError(
                    f"EngineRowResult must be a dict or FHIRAbstractModel, got: {resource}"
                )
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
        return self.bundle_model.model_validate(self.data)

    def resolve_absolute_uri(self, relative_path: str) -> URL:
        """ """
        try:
            resource, id = relative_path.split("/")
        except ValueError:
            raise ValueError(
                f"'{relative_path}' is not valid relative path. "
                "Format 'ResourceType/ResourceID'"
            )
        return self.base_url / resource / id

    def json(self):
        """ """
        return self.__call__().model_dump_json()


def get_local_timezone() -> datetime.timezone:
    if LOCAL_TIMEZONE is not None:
        return LOCAL_TIMEZONE

    is_dst = time.daylight and time.localtime().tm_isdst > 0
    seconds = -(time.altzone if is_dst else time.timezone)
    tz = datetime.timezone(datetime.timedelta(seconds=seconds))
    return tz


def timestamp_utc() -> datetime.datetime:
    """UTC datetime with timezone offset"""
    dt_now = datetime.datetime.utcnow()
    return dt_now.replace(tzinfo=datetime.timezone.utc)


def timestamp_local() -> datetime.datetime:
    """Timezone aware datetime with local timezone offset"""
    return datetime.datetime.now(tz=get_local_timezone())
