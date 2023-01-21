# _*_ coding: utf-8 _*_
import datetime
import inspect
import os
import pkgutil
import re
import sys
import time
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
)

import pkg_resources

from fhirpath.thirdparty import Proxy
from .enums import FHIR_VERSION
from .json import json_dumps, json_loads  # noqa: F401

if TYPE_CHECKING:
    from fhir.resources.core.fhirabstractmodel import FHIRAbstractModel

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

def lookup_all_fhir_domain_resource_classes(
    fhir_release: FHIR_VERSION = FHIR_VERSION.DEFAULT,
) -> Dict[str, str]:
    """ """
    container: Dict[str, str] = {}
    fhir_release = FHIR_VERSION.normalize(fhir_release)
    pkg = "fhir.resources"
    if fhir_release.name != FHIR_VERSION.DEFAULT.value:
        pkg += f".{fhir_release.name}"

    prime_module_type: ModuleType = import_module(pkg)

    for _importer, module_name, ispkg in pkgutil.walk_packages(
        prime_module_type.__path__,  # type: ignore
        prime_module_type.__name__ + ".",
        onerror=lambda x: None,
    ):
        if ispkg or (len(pkg.split(".")) + 1) < len(module_name.split(".")):
            continue

        module_type: ModuleType = import_module(module_name)

        for klass_name, _klass in inspect.getmembers(module_type, inspect.isclass):
            if inspect.getmro(_klass)[1].__name__ != "DomainResource":
                continue

            container[klass_name] = f"{_klass.__module__}.{klass_name}"
    return container


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
