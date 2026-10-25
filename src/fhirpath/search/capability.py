# _*_ coding: utf-8 _*_
"""The search part of a ``CapabilityStatement`` (FHIR R5 search §3.2.1.10):
``rest.resource.searchParam`` / ``searchInclude`` / ``searchRevInclude`` and
the system-wide ``rest.searchParam``, for the parameters this package can
search on."""

import datetime
from typing import Any, Dict, Iterable, List, Optional

from fhirpath.enums import FHIR_VERSION
from fhirpath.search.exceptions import ValidationError
from fhirpath.search.storage import SEARCH_PARAMETERS_STORAGE

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

# parameters handled by the search itself rather than by an element path
HANDLED_PARAMETERS = {
    "_text",
    "_content",
    "_filter",
    "_query",
    "_list",
    "_has",
    "_type",
    "_in",
    "near",
    "near-distance",
}
# described by the specification but not in every release's definitions
SPECIAL_PARAMETERS = {
    "_filter": "https://hl7.org/fhir/search_filter.html",
    "_has": "https://hl7.org/fhir/search.html#has",
    "_list": "https://hl7.org/fhir/search.html#list",
    "_type": "https://hl7.org/fhir/search.html#type",
}


def _storage(engine):
    from fhirpath.search.search import SearchContext

    # makes sure the definitions are loaded
    SearchContext(engine, None)
    return SEARCH_PARAMETERS_STORAGE.get(
        FHIR_VERSION.normalize(engine.fhir_release).name
    )


def is_supported(engine, resource_type: str, search_param) -> bool:
    """Whether a search on the parameter can be built."""
    from fhirpath.search.fhirspec.expression import (
        UnsupportedExpression,
        component_paths,
        computed_presence_path,
    )
    from fhirpath.search.search import SearchContext

    if search_param.code in HANDLED_PARAMETERS:
        return True
    if not search_param.expression:
        return False
    context = SearchContext(engine, resource_type)
    try:
        if search_param.type == "composite":
            for base in search_param.element_paths():
                for component in search_param.component or []:
                    context.dotted_paths_to_path_contexts(
                        component_paths(base, component["expression"])
                    )
            return True
        if search_param.type == "token" and computed_presence_path(
            search_param.expression
        ):
            return True
        context.resolve_path_contexts(search_param)
    except (
        NotImplementedError,
        UnsupportedExpression,
        ValidationError,
        KeyError,
        AttributeError,
        LookupError,
    ):
        return False
    return True


def _search_param(search_param) -> Dict[str, Any]:
    entry = {"name": search_param.code, "type": search_param.type}
    if search_param.url:
        entry["definition"] = search_param.url
    return entry


def resource_search_capabilities(
    engine, resource_type: str, reverse: Optional[Dict[str, List[str]]] = None
) -> Dict[str, Any]:
    """``CapabilityStatement.rest.resource`` of a resource type."""
    definition = _storage(engine).get(resource_type)
    params = []
    includes = ["*", f"{resource_type}:*"]
    for code in sorted(definition):
        search_param = getattr(definition, code)
        if not is_supported(engine, resource_type, search_param):
            continue
        params.append(_search_param(search_param))
        if search_param.type == "reference" and search_param.expression:
            includes.append(f"{resource_type}:{code}")
    resource = {
        "type": resource_type,
        "interaction": [{"code": "search-type"}],
        "searchInclude": includes,
        "searchParam": params,
    }
    if reverse is not None:
        resource["searchRevInclude"] = ["*", *sorted(reverse.get(resource_type, []))]
    return resource


def reverse_includes(engine, resource_types: Iterable[str]) -> Dict[str, List[str]]:
    """``Source:param`` of every reference parameter, per target type."""
    from fhirpath.search.search import reference_targets

    storage = _storage(engine)
    wanted = set(resource_types)
    reverse: Dict[str, List[str]] = {}
    for source_type in storage:
        if source_type in ("Resource", "DomainResource"):
            continue
        definition = storage.get(source_type)
        for code in definition:
            search_param = getattr(definition, code)
            if search_param.type != "reference" or not search_param.expression:
                continue
            for target in reference_targets(search_param):
                if target in wanted:
                    reverse.setdefault(target, []).append(f"{source_type}:{code}")
    return reverse


def search_capabilities(
    engine, resource_types: Optional[Iterable[str]] = None
) -> Dict[str, Any]:
    """``CapabilityStatement.rest`` (mode ``server``) for searching
    ``resource_types`` (default: every resource type of the release)."""
    from fhirpath.search.search import NAMED_QUERY_DEFINITIONS

    storage = _storage(engine)
    types = sorted(
        resource_types
        or (t for t in storage if t not in ("Resource", "DomainResource"))
    )
    reverse = reverse_includes(engine, types)
    common = storage.get("Resource")
    system_params = [
        _search_param(getattr(common, code))
        for code in sorted(common)
        if is_supported(engine, "Resource", getattr(common, code))
    ]
    known = {p["name"] for p in system_params}
    for code, url in sorted(SPECIAL_PARAMETERS.items()):
        if code not in known:
            system_params.append({"name": code, "definition": url, "type": "special"})
    rest: Dict[str, Any] = {
        "mode": "server",
        "resource": [resource_search_capabilities(engine, t, reverse) for t in types],
        "interaction": [{"code": "search-system"}],
        "searchParam": system_params,
    }
    if NAMED_QUERY_DEFINITIONS:
        # named queries (_query) are query operations
        rest["operation"] = [
            {"name": name, "definition": definition}
            for name, definition in sorted(NAMED_QUERY_DEFINITIONS.items())
        ]
    return rest


def capability_statement(
    engine,
    resource_types: Optional[Iterable[str]] = None,
    software_name: str = "fhirpath",
) -> Dict[str, Any]:
    """A ``CapabilityStatement`` (as a dict) describing the search
    capabilities; complete or extend it with the server's other interactions."""
    release = FHIR_VERSION.normalize(engine.fhir_release)
    statement = {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds"
        ),
        "kind": "instance",
        "software": {"name": software_name},
        "implementation": {"description": f"{software_name} FHIR search"},
        "fhirVersion": release.value,
        "format": ["json"],
        "rest": [search_capabilities(engine, resource_types)],
    }
    if release == FHIR_VERSION.STU3:
        # required in STU3 only
        statement["acceptUnknown"] = "no"
    return statement
