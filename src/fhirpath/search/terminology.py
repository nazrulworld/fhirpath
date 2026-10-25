# _*_ coding: utf-8 _*_
"""Terminology for token searches: value set expansion (``:in``, ``:not-in``)
and subsumption (``:below``, ``:above``).

:class:`InMemoryTerminology` works on ``ValueSet`` and ``CodeSystem`` resources
(dicts) - by default the ones published with the FHIR release, plus any the
application registers. An engine can provide its own service (e.g. one backed
by a terminology server) as its ``terminology`` attribute; it only needs the two
methods of :class:`TerminologyService`.
"""
import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlsplit

from fhirpath.enums import FHIR_VERSION
from fhirpath.search.exceptions import ValidationError

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.search.terminology")

Code = Tuple[Optional[str], str]  # (system, code)


class TerminologyService:
    """What token searches need from a terminology."""

    def expand(self, valueset: str) -> List[Code]:
        """The ``(system, code)`` members of a value set, given by literal
        reference (``ValueSet/123``), canonical url or implicit url
        (``http://snomed.info/sct?fhir_vs=isa/235862008``). Raises
        ``ValidationError`` for an unknown value set."""
        raise NotImplementedError

    def subsumption(
        self, system: Optional[str], code: str, direction: str
    ) -> List[Code]:
        """``code`` and its descendants (``direction='below'``) or ancestors
        (``'above'``). Raises ``ValidationError`` when the code system's
        hierarchy is unknown."""
        raise NotImplementedError


class InMemoryTerminology(TerminologyService):
    """Value sets and code systems held in memory."""

    def __init__(
        self,
        resources: Iterable[Dict[str, Any]] = (),
        fhir_release: Optional[FHIR_VERSION] = None,
    ):
        self.valuesets: Dict[str, Dict[str, Any]] = {}
        self.codesystems: Dict[str, Dict[str, Any]] = {}
        # system -> code -> parent codes / child codes
        self._parents: Dict[str, Dict[str, Set[str]]] = {}
        self._children: Dict[str, Dict[str, Set[str]]] = {}
        self._fhir_release = fhir_release
        self._release_loaded = fhir_release is None
        for resource in resources:
            self.register(resource)

    # ------------------------------------------------------------ resources

    def register(self, resource: Dict[str, Any]):
        """Add a ``ValueSet`` or ``CodeSystem`` (or a ``Bundle`` of them)."""
        resource_type = resource.get("resourceType")
        if resource_type == "Bundle":
            for entry in resource.get("entry", []):
                if "resource" in entry:
                    self.register(entry["resource"])
        elif resource_type == "ValueSet":
            if resource.get("url"):
                self.valuesets[resource["url"]] = resource
            if resource.get("id"):
                self.valuesets[f"ValueSet/{resource['id']}"] = resource
        elif resource_type == "CodeSystem":
            if resource.get("url"):
                self.codesystems[resource["url"]] = resource
                # only a complete code system knows all codes and relations
                if resource.get("content", "complete") == "complete":
                    self._index_hierarchy(resource)
            if resource.get("valueSet"):
                # the "all codes" value set of the code system
                self.valuesets.setdefault(
                    resource["valueSet"],
                    {
                        "resourceType": "ValueSet",
                        "url": resource["valueSet"],
                        "compose": {"include": [{"system": resource["url"]}]},
                    },
                )

    def _ensure_release(self):
        if self._release_loaded:
            return
        self._release_loaded = True
        from fhirpath.search.fhirspec import SPEC_JSON_DIR, ensure_spec_jsons

        release = FHIR_VERSION.normalize(self._fhir_release)
        ensure_spec_jsons(release)
        path = SPEC_JSON_DIR / release.name / release.value / "valuesets.min.json"
        try:
            with open(str(path), encoding="utf-8") as fp:
                bundle = json.load(fp)
        except OSError:  # pragma: no cover - definitions not available
            logger.warning(f"no value sets for FHIR {release.name} at {path}")
            return
        known_valuesets, known_codesystems = self.valuesets, self.codesystems
        self.valuesets, self.codesystems = {}, {}
        self.register(bundle)
        # resources registered by the application win
        self.valuesets.update(known_valuesets)
        self.codesystems.update(known_codesystems)

    def _index_hierarchy(self, codesystem: Dict[str, Any]):
        system = codesystem["url"]
        parents = self._parents.setdefault(system, {})
        children = self._children.setdefault(system, {})

        def link(parent: str, child: str):
            parents.setdefault(child, set()).add(parent)
            children.setdefault(parent, set()).add(child)

        def walk(concepts, parent=None):
            for concept in concepts or []:
                code = concept.get("code")
                if code is None:
                    continue
                parents.setdefault(code, set())
                children.setdefault(code, set())
                if parent is not None:
                    link(parent, code)
                for prop in concept.get("property", []):
                    other = prop.get("valueCode")
                    if other is None:
                        continue
                    if prop.get("code") in ("parent", "subsumedBy"):
                        link(other, code)
                    elif prop.get("code") == "child":
                        link(code, other)
                walk(concept.get("concept"), code)

        walk(codesystem.get("concept"))

    # --------------------------------------------------------- subsumption

    def _closure(self, system: str, code: str, direction: str) -> List[str]:
        graph = (self._children if direction == "below" else self._parents)[system]
        seen = [code]
        pending = [code]
        while pending:
            for other in sorted(graph.get(pending.pop(), ())):
                if other not in seen:
                    seen.append(other)
                    pending.append(other)
        return seen

    def subsumption(
        self, system: Optional[str], code: str, direction: str
    ) -> List[Code]:
        self._ensure_release()
        if system is None:
            systems = [s for s, codes in self._parents.items() if code in codes]
            if not systems:
                raise ValidationError(
                    f"``:{direction}`` needs a known code system for code ``{code}``."
                )
        elif system in self._parents:
            systems = [system]
        else:
            raise ValidationError(
                f"``:{direction}`` is not supported for code system ``{system}``: "
                "its hierarchy is unknown."
            )
        # a code unknown to a known system subsumes only itself
        return [(s, c) for s in systems for c in self._closure(s, code, direction)]

    # ----------------------------------------------------------- expansion

    def expand(self, valueset: str) -> List[Code]:
        self._ensure_release()
        literal = literal_valueset_reference(valueset)
        if valueset not in self.valuesets and literal in self.valuesets:
            valueset = literal
        return self._expand(valueset, [])

    def _expand(self, url: str, stack: List[str]) -> List[Code]:
        if url in stack:
            raise ValidationError(f"value set ``{url}`` includes itself")
        resource = self.valuesets.get(url)
        if resource is None and "|" in url:
            # versioned canonical
            resource = self.valuesets.get(url.split("|", 1)[0])
        if resource is None:
            implicit = self._implicit(url)
            if implicit is not None:
                return implicit
            raise ValidationError(f"Unknown value set ``{url}``.")
        stack = [*stack, url]

        expansion = resource.get("expansion", {})
        if expansion.get("contains"):
            return list(dict.fromkeys(self._flatten(expansion["contains"])))

        compose = resource.get("compose", {})
        included: List[Code] = []
        for include in compose.get("include", []):
            included.extend(self._include(include, stack))
        excluded = set()
        for exclude in compose.get("exclude", []):
            excluded.update(self._include(exclude, stack))
        return [c for c in dict.fromkeys(included) if c not in excluded]

    def _flatten(self, contains) -> Iterable[Code]:
        for item in contains:
            if item.get("code") and not item.get("abstract"):
                yield item.get("system"), item["code"]
            yield from self._flatten(item.get("contains", []))

    def _implicit(self, url: str) -> Optional[List[Code]]:
        """``[system]?fhir_vs`` (all codes) and ``[system]?fhir_vs=isa/[code]``."""
        if "?fhir_vs" not in url:
            return None
        system, _, query = url.partition("?")
        rule = parse_qs(query, keep_blank_values=True).get("fhir_vs", [""])[0]
        if not rule:
            return self._all_codes(system)
        if rule.startswith("isa/"):
            return self.subsumption(system, rule[4:], "below")
        raise ValidationError(f"Unsupported implicit value set ``{url}``.")

    def _all_codes(self, system: str) -> List[Code]:
        if system not in self._parents:
            raise ValidationError(
                f"The codes of code system ``{system}`` are unknown "
                "(value set expansion)."
            )
        return [(system, code) for code in self._parents[system]]

    def _include(self, include: Dict[str, Any], stack: List[str]) -> List[Code]:
        system = include.get("system")
        codes: Optional[List[Code]] = None
        if include.get("concept"):
            codes = [(system, c["code"]) for c in include["concept"] if c.get("code")]
        elif include.get("filter"):
            for filter_ in include["filter"]:
                selected = self._filter(system, filter_)
                codes = (
                    selected
                    if codes is None
                    else [c for c in codes if c in set(selected)]
                )
        elif system:
            codes = self._all_codes(system)

        for valueset in include.get("valueSet", []):
            members = self._expand(valueset, stack)
            codes = members if codes is None else [c for c in codes if c in members]
        return codes or []

    def _filter(self, system: Optional[str], filter_: Dict[str, Any]) -> List[Code]:
        prop, op, value = (
            filter_.get("property"),
            filter_.get("op"),
            filter_.get("value"),
        )
        if prop == "concept" and op in ("is-a", "descendent-of", "generalizes"):
            direction = "above" if op == "generalizes" else "below"
            codes = self.subsumption(system, value, direction)
            if op == "descendent-of":
                codes = [c for c in codes if c[1] != value]
            return codes
        if prop == "concept" and op in ("is-not-a",):
            excluded = set(self.subsumption(system, value, "below"))
            return [c for c in self._all_codes(system) if c not in excluded]
        if prop == "concept" and op == "in":
            wanted = {v.strip() for v in value.split(",")}
            return [(system, c) for c in wanted]
        if op == "=" and prop in ("code", "concept"):
            return [(system, value)]
        raise ValidationError(
            f"Unsupported value set filter ``{prop} {op} {value}`` "
            f"(system ``{system}``)."
        )


_DEFAULT_TERMINOLOGIES: Dict[str, InMemoryTerminology] = {}


def get_terminology(engine) -> TerminologyService:
    """The engine's terminology (``engine.terminology``) or the value sets and
    code systems of its FHIR release."""
    terminology = getattr(engine, "terminology", None)
    if terminology is not None:
        return terminology
    release = FHIR_VERSION.normalize(engine.fhir_release)
    if release.name not in _DEFAULT_TERMINOLOGIES:
        _DEFAULT_TERMINOLOGIES[release.name] = InMemoryTerminology(
            fhir_release=release
        )
    return _DEFAULT_TERMINOLOGIES[release.name]


def literal_valueset_reference(value: str) -> str:
    """``ValueSet/123`` and ``[base]/ValueSet/123`` -> ``ValueSet/123``; other
    values (canonical urls) are kept."""
    parts = urlsplit(value)
    segments = parts.path.rstrip("/").split("/")
    if len(segments) >= 2 and segments[-2] == "ValueSet" and not parts.query:
        return f"ValueSet/{segments[-1]}"
    return value
