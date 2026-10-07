# _*_ coding: utf-8 _*_
"""Functions defined by the FHIR specification (https://hl7.org/fhir/fhirpath.html)."""

from html.parser import HTMLParser
from typing import Any, List, Optional

from ..model import Node, lookup_class
from ..values import MISSING, system
from .registry import Call, function

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


@function("extension", 1)
def extension(call: Call):
    url = call.arg_string(0)
    if url is MISSING:
        return []
    result: List[Any] = []
    for item in call.input:
        if isinstance(item, Node):
            result.extend(
                ext for ext in item.child("extension") if ext.get("url") == url
            )
    return result


@function("hasValue")
def has_value(call: Call):
    if len(call.input) != 1:
        return [False]
    item = call.input[0]
    if isinstance(item, Node):
        return [item.has_value()]
    return [False]


@function("getValue")
def get_value(call: Call):
    if len(call.input) != 1:
        return []
    item = call.input[0]
    if isinstance(item, Node) and item.has_value():
        return [item.to_system()]
    return []


# ------------------------------------------------------------------ resolve()


def _reference_text(item: Any) -> Optional[str]:
    if isinstance(item, Node):
        if item.is_primitive:
            value = item.to_system()
            return value if isinstance(value, str) else None
        reference = item.get("reference")
        return reference if isinstance(reference, str) else None
    return item if isinstance(item, str) else None


def _candidates(start: Node) -> List[Node]:
    """Resources reachable for local resolution: containers, contained, Bundle entries."""
    resources: List[Node] = []
    node: Optional[Node] = start
    while node is not None:
        if node.is_resource:
            resources.append(node)
            resources.extend(node.child("contained"))
            if node.type_name == "Bundle":
                for entry in node.child("entry"):
                    resources.extend(entry.child("resource"))
        node = node.parent
    return resources


def _bundle_entries(start: Node):
    node: Optional[Node] = start
    while node is not None:
        if node.type_name == "Bundle":
            for entry in node.child("entry"):
                full_url = entry.get("fullUrl")
                for resource in entry.child("resource"):
                    yield full_url, resource
        node = node.parent


def _resolve_one(call: Call, reference: str, origin: Optional[Node]) -> Optional[Node]:
    if origin is not None:
        if reference.startswith("#"):
            target_id = reference[1:]
            container = origin.resource_node()
            # walk up to the resource that holds the contained resources
            while (
                container is not None
                and container.name == "contained"
                and container.parent is not None
            ):
                container = container.parent.resource_node()
            if container is not None:
                if not target_id:
                    return container
                for contained in container.child("contained"):
                    if contained.get("id") == target_id:
                        return contained
        for full_url, resource in _bundle_entries(origin):
            if full_url == reference:
                return resource
            if full_url and reference and full_url.endswith("/" + reference):
                return resource
        for resource in _candidates(origin):
            rid = resource.get("id")
            if rid is not None and reference in ("%s/%s" % (resource.type_name, rid),):
                return resource
    resolver = call.ctx.env.resolver
    if resolver is not None:
        target = resolver(reference, origin)
        if target is not None:
            return target if isinstance(target, Node) else Node.root(target)
    return None


@function("resolve")
def resolve(call: Call):
    result: List[Any] = []
    for item in call.input:
        reference = _reference_text(item)
        if not reference:
            continue
        origin = item if isinstance(item, Node) else None
        if origin is None:
            context = call.ctx.variables.get("resource") or []
            origin = context[0] if context and isinstance(context[0], Node) else None
        target = _resolve_one(call, reference, origin)
        if target is not None:
            result.append(target)
    return result


# --------------------------------------------------------------- terminology


def _terminology(call: Call):
    service = call.ctx.env.terminology
    if service is None:
        raise call.error("no terminology service configured")
    return service


@function("memberOf", 1)
def member_of(call: Call):
    valueset = call.arg_string(0)
    item = call.input_item() if len(call.input) <= 1 else MISSING
    if valueset is MISSING or item is MISSING:
        return []
    outcome = _terminology(call).member_of(system(item), valueset)
    return [] if outcome is None else [outcome]


def _subsumption(call: Call, reverse: bool):
    if len(call.input) != 1:
        return []
    other = call.arg(0)
    if len(other) != 1:
        return []
    service = _terminology(call)
    left, right = (other[0], call.input[0]) if reverse else (call.input[0], other[0])
    codings_l, codings_r = _codings(left), _codings(right)
    for system_a, code_a in codings_l:
        for system_b, code_b in codings_r:
            if system_a == system_b:
                outcome = service.subsumes(system_a, code_a, code_b)
                if outcome:
                    return [True]
    return [False] if codings_l and codings_r else []


def _codings(item: Any):
    if not isinstance(item, Node):
        return []
    if item.type_name == "CodeableConcept":
        return [c for coding in item.child("coding") for c in _codings(coding)]
    if item.type_name == "Coding":
        return [(item.get("system"), item.get("code"))]
    return []


@function("subsumes", 1)
def subsumes(call: Call):
    return _subsumption(call, reverse=False)


@function("subsumedBy", 1)
def subsumed_by(call: Call):
    return _subsumption(call, reverse=True)


# --------------------------------------------------------------------- misc


class _NarrativeChecker(HTMLParser):
    """FHIR narrative rules: only the basic XHTML element set, no scripts/event handlers."""

    ALLOWED = frozenset(
        "a abbr acronym b big blockquote br caption cite code col colgroup dd dfn div dl dt em "
        "h1 h2 h3 h4 h5 h6 hr i img li ol p pre q samp small span strong sub sup table tbody "
        "td tfoot th thead tr tt ul var".split()
    )

    def __init__(self):
        HTMLParser.__init__(self)
        self.ok = True

    def handle_starttag(self, tag, attrs):
        if tag not in self.ALLOWED:
            self.ok = False
        for name, value in attrs:
            if name.lower().startswith("on") or (
                value or ""
            ).strip().lower().startswith("javascript:"):
                self.ok = False


@function("htmlChecks")
def html_checks(call: Call):
    value = call.input_value()
    if value is MISSING or not isinstance(value, str):
        return []
    checker = _NarrativeChecker()
    try:
        checker.feed(value)
        checker.close()
    except Exception:  # noqa: B902 - malformed markup
        return [False]
    return [checker.ok]


@function("checkModifiers", 1)
def check_modifiers(call: Call):
    allowed = call.arg_string(0)
    allowed_urls = set(u.strip() for u in (allowed or "").split(",") if u.strip())
    for item in call.input:
        if isinstance(item, Node):
            for modifier in item.child("modifierExtension"):
                if modifier.get("url") not in allowed_urls:
                    raise call.error(
                        "unknown modifier extension %s" % modifier.get("url")
                    )
    return list(call.input)


def _unsupported(name: str, min_args: int, max_args: int):
    def impl(call: Call):
        raise call.error(
            "not supported by this engine (requires a validator/profile resolver)"
        )

    function(name, min_args, max_args)(impl)


_CORE_PROFILE = "http://hl7.org/fhir/StructureDefinition/"


@function("conformsTo", 1)
def conforms_to(call: Call):
    """Base FHIR profiles only: conformance to a core type's StructureDefinition.

    Other profiles need a validator and signal an error.
    """
    structure = call.arg_string(0)
    if (
        structure is MISSING
        or len(call.input) != 1
        or not isinstance(call.input[0], Node)
    ):
        return []
    if not structure.startswith(_CORE_PROFILE):
        raise call.error("only core FHIR profiles are supported, got %s" % structure)
    type_name = structure[len(_CORE_PROFILE) :]
    if lookup_class(type_name) is None:
        return []
    return [type_name in call.input[0].type_names()]


_unsupported("elementDefinition", 0, 0)
_unsupported("slice", 2, 2)
_unsupported("weight", 0, 0)


@function("pathname", 0, 1)
def pathname(call: Call):
    return [
        item.path()
        for item in call.input
        if isinstance(item, Node) and item.name is not None
    ]
