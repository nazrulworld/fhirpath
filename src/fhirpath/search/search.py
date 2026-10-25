# _*_ coding: utf-8 _*_
import logging
import re
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generator,
    List,
    NamedTuple,
    Optional,
    Pattern,
    Set,
    Tuple,
    Type,
    Union,
)
from urllib.parse import unquote_plus
from warnings import warn

from multidict import MultiDict, MultiDictProxy
from zope.interface import implementer

from fhirpath.core import ast as fhirpath_ast
from fhirpath.core.parser import FHIRPathSyntaxError
from fhirpath.core.parser import parse as fhirpath_parse
from fhirpath.core import compile as fhirpath_compile
from fhirpath.search.engine import (
    EngineResult,
    EngineResultBody,
    EngineResultHeader,
    EngineResultRow,
)
from fhirpath.search.engine.base import resolve_literal_reference
from fhirpath.enums import (
    FHIR_VERSION,
    GroupType,
    MatchType,
    SortOrderType,
    TermMatchType,
    WhereConstraintType,
)
from fhirpath.search.exceptions import ValidationError
from fhirpath.search.fhirspec.expression import (
    UnsupportedExpression,
    component_paths,
    computed_presence_path,
)
from fhirpath.search.fhirspec import (
    FHIRSearchSpecFactory,
    ResourceSearchParameterDefinition,
    SearchParameter,
    lookup_fhir_resource_spec,
    search_param_prefixes,
)
from fhirpath.search.fql import (
    G_,
    T_,
    V_,
    contains_,
    eb_,
    exact_,
    exists_,
    not_,
    not_exists_,
    sa_,
    sort_,
)
from fhirpath.search.fql.types import ElementPath
from fhirpath.search.ranges import (
    DATE_PREFIX_BOUNDS,
    DATE_TYPES,
    NUMBER_TYPES,
    approximate_date_range,
    date_bound,
    date_bounds,
    number_bounds,
)
from fhirpath.search.interfaces import IGroupTerm, ISearch, ISearchContext
from fhirpath.search.query import Q_, QueryResult
from fhirpath.search.storage import SEARCH_PARAMETERS_STORAGE
from fhirpath.search.graph import resolve_graph
from fhirpath.search.terminology import get_terminology
from fhirpath.search.utils import PathInfoContext, lookup_fhir_class

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

uri_scheme: Pattern = re.compile(r"^https?://", re.I)
value_prefixes: Set[str] = {"eq", "ne", "gt", "lt", "ge", "le", "sa", "eb", "ap"}
has_dot_as: Pattern = re.compile(r"\.as\([a-z]+\)$", re.I ^ re.U)
has_dot_is: Pattern = re.compile(r"\.is\([a-z]+\)$", re.I ^ re.U)
has_dot_where: Pattern = re.compile(r"\.where\([a-z=\'\"()]+\)", re.I ^ re.U)
parentheses_wrapped: Pattern = re.compile(r"^\(.+\)$")
logger = logging.getLogger("fhirpath.search")

DEFAULT_RESULT_COUNT = 100
# rounds of ``_include:iterate`` / ``_revinclude:iterate``
INCLUDE_MAX_ITERATIONS = 10
# levels followed by ``reference:below`` / ``reference:above``
HIERARCHY_MAX_DEPTH = 32
TOTAL_VALUES = ("none", "estimate", "accurate")
SUMMARY_VALUES = ("true", "text", "data", "count", "false")
# meta.tag of a resource returned with only some of its elements
SUBSETTED_TAG = {
    "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
    "code": "SUBSETTED",
    "display": "Resource encoded in summary mode",
}
# how unknown search parameters are treated (``Prefer: handling=…``)
HANDLING_LENIENT = "lenient"
HANDLING_STRICT = "strict"
# Quantity and its profiles (searched like a Quantity)
QUANTITY_TYPES = (
    "Quantity",
    "Age",
    "Count",
    "Distance",
    "Duration",
    "MoneyQuantity",
    "SimpleQuantity",
)
# modifiers per parameter type (FHIR R5 search §3.2.1.5.5); non-standard:
# "exists" (the inverse of "missing") and "not" on string, uri and reference
# parameters. Any other modifier is rejected
SUPPORTED_MODIFIERS: Dict[str, Set[str]] = {
    "string": {"missing", "exists", "not", "exact", "contains", "text"},
    "token": {
        "missing",
        "exists",
        "not",
        "text",
        "in",
        "not-in",
        "below",
        "above",
        "of-type",
        "code-text",
        "text-advanced",
    },
    "uri": {"missing", "exists", "not", "below", "above", "contains"},
    "reference": {
        "missing",
        "exists",
        "not",
        "identifier",
        "below",
        "above",
        "text",
        "code-text",
        "text-advanced",
    },
    "number": {"missing", "exists"},
    "date": {"missing", "exists"},
    "quantity": {"missing", "exists"},
    "special": {"missing", "exists"},
}
# modifiers introduced after STU3, with the first release that has them
MODIFIER_SINCE: Dict[str, FHIR_VERSION] = {
    "of-type": FHIR_VERSION.R4,
    "identifier": FHIR_VERSION.R4,
    "code-text": FHIR_VERSION.R5,
    "text-advanced": FHIR_VERSION.R5,
}
RELEASE_ORDER = (FHIR_VERSION.STU3, FHIR_VERSION.R4, FHIR_VERSION.R4B, FHIR_VERSION.R5)


def map_normalized_values(values, func):
    """Replace every ``(prefix, value)`` leaf of a normalized parameter value
    (leaves, OR tuples ``(None, [...])``, AND lists) by ``func(leaf)``."""
    if isinstance(values, list):
        return [map_normalized_values(v, func) for v in values]
    operator_, value = values
    if isinstance(value, list):
        return (operator_, [map_normalized_values(v, func) for v in value])
    return func(values)


def plain_reference_id(value: str) -> bool:
    """``123`` (as opposed to ``Patient/123``, an absolute URL or ``url|version``)."""
    return "/" not in value and ":" not in value and not has_unescaped(value, "|")


def typed_reference_leaf(types: List[str], leaf):
    """A plain id stands for a reference to any of ``types``: ``123`` ->
    ``Patient/123`` (or ``Patient/123,Group/123``)."""
    operator_, value = leaf
    if not types or not plain_reference_id(value):
        return leaf
    if len(types) == 1:
        return (operator_, f"{types[0]}/{value}")
    return (None, [(operator_, f"{t}/{value}") for t in types])


local_reference = re.compile(
    r"^(?P<type>[A-Z][A-Za-z]+)/(?P<id>[A-Za-z0-9\-.]{1,64})"
    r"(?P<history>/_history/[A-Za-z0-9\-.]{1,64})?$"
)


def reference_variants(value: str, base: Optional[str]) -> List[Tuple[str, str]]:
    """Stored references equivalent to a reference search value, as
    ``(operator, value)``: ``Patient/123`` matches ``Patient/123``, the absolute
    url on this server and ``Patient/123/_history/…`` (``sa``: prefix);
    ``[base]/Patient/123`` matches itself and ``Patient/123``."""
    match = local_reference.match(value)
    if match is not None:
        variants = [("eq", value)]
        if base:
            variants.append(("eq", f"{base}/{value}"))
        if not match.group("history"):
            variants.append(("sa", f"{value}/_history/"))
        return variants
    if base and value.startswith(base + "/"):
        relative = value[len(base) + 1 :]
        match = local_reference.match(relative)
        if match is not None and not match.group("history"):
            return [("eq", value), ("eq", relative)]
    return [("eq", value)]


def typed_reference_value(resource_type: str, value: str) -> str:
    """Value of a ``[type]`` modified reference parameter as ``Type/id``."""
    if value.startswith(f"{resource_type}/"):
        return value
    if "/" in value:
        raise ValidationError(
            f"``:{resource_type}`` modifier expects a resource id, got ``{value}``."
        )
    return f"{resource_type}/{value}"


# string parts of complex types searched by string parameters
HUMANNAME_STRING_ELEMENTS = ("text", "family", "given", "prefix", "suffix")
ADDRESS_STRING_ELEMENTS = (
    "text",
    "line",
    "city",
    "district",
    "state",
    "postalCode",
    "country",
)

# value[x] types an extension value is searched on, per search parameter type
EXTENSION_VALUE_TYPES: Dict[str, List[str]] = {
    "string": ["valueString", "valueMarkdown"],
    "token": [
        "valueCode",
        "valueCoding",
        "valueCodeableConcept",
        "valueBoolean",
        "valueIdentifier",
        "valueString",
        "valueId",
    ],
    "reference": ["valueReference", "valueCanonical", "valueUri"],
    "uri": ["valueUri", "valueUrl", "valueCanonical"],
    "date": ["valueDate", "valueDateTime", "valueInstant", "valuePeriod"],
    "number": ["valueInteger", "valueDecimal", "valuePositiveInt", "valueUnsignedInt"],
    "quantity": ["valueQuantity", "valueAge", "valueDuration", "valueRange"],
}

# characters a backslash may escape in a search value (after URL decoding)
ESCAPABLE_CHARS = frozenset(",$|\\")


def validate_escapes(value: str):
    """A ``\\`` must escape one of ``, $ | \\``; anything else is illegal."""
    index = 0
    while index < len(value):
        if value[index] == "\\":
            if index + 1 >= len(value) or value[index + 1] not in ESCAPABLE_CHARS:
                raise ValidationError(
                    f"Illegal escape sequence in search value ``{value}``: "
                    "a backslash may only escape ``,``, ``$``, ``|`` or ``\\``."
                )
            index += 2
        else:
            index += 1


def split_escaped(value: str, separator: str) -> List[str]:
    """Split on ``separator`` unless escaped; the parts keep their escapes."""
    parts: List[str] = []
    current: List[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            current.append(value[index : index + 2])
            index += 2
            continue
        if char == separator:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    parts.append("".join(current))
    return parts


def handling_from_prefer(prefer: Optional[str]) -> str:
    """``handling`` of a ``Prefer`` HTTP header (``return=minimal,
    handling=strict`` -> ``strict``); lenient when absent or unrecognised."""
    for part in re.split(r"[,;]", prefer or ""):
        name, _, value = part.partition("=")
        if name.strip().lower() == "handling":
            value = value.strip().strip('"').lower()
            if value in (HANDLING_LENIENT, HANDLING_STRICT):
                return value
    return HANDLING_LENIENT


def escape_value(value: str) -> str:
    """Inverse of ``unescape_value``: ``a,b`` -> ``a\\,b``."""
    return "".join("\\" + c if c in ESCAPABLE_CHARS else c for c in value)


def has_unescaped(value: str, separator: str) -> bool:
    return len(split_escaped(value, separator)) > 1


def unescape_value(value):
    """``a\\,b`` -> ``a,b`` (only ``, $ | \\`` are escapable)."""
    if not isinstance(value, str) or "\\" not in value:
        return value
    result: List[str] = []
    index = 0
    while index < len(value):
        if (
            value[index] == "\\"
            and index + 1 < len(value)
            and value[index + 1] in ESCAPABLE_CHARS
        ):
            result.append(value[index + 1])
            index += 2
        else:
            result.append(value[index])
            index += 1
    return "".join(result)


# A chain resolver yields the sub-queries it needs and receives their results,
# so that ``Search`` and ``AsyncSearch`` can share the same resolution logic.
ChainResolver = Generator[QueryResult, EngineResult, List[str]]


def run_chain_resolver(resolver: ChainResolver) -> List[str]:
    """Drive a chain resolver with blocking queries."""
    try:
        query = next(resolver)
        while True:
            query = resolver.send(query.fetchall())
    except StopIteration as stop:
        return stop.value


def _resolve_is_types(node: fhirpath_ast.Node) -> Optional[Set[str]]:
    """Types ``X`` that ``….where(resolve() is X)`` restricts every union branch
    of a FHIRPath expression to; ``None`` if any branch is unrestricted."""
    if isinstance(node, fhirpath_ast.Binary) and node.op == "|":
        left = _resolve_is_types(node.left)
        right = _resolve_is_types(node.right)
        if left is None or right is None:
            return None
        return left | right
    if isinstance(node, fhirpath_ast.Invocation):
        where = node.right
        if (
            isinstance(where, fhirpath_ast.Function)
            and where.name == "where"
            and len(where.args) == 1
        ):
            test = where.args[0]
            if (
                isinstance(test, fhirpath_ast.TypeOperation)
                and test.op == "is"
                and isinstance(test.left, fhirpath_ast.Function)
                and test.left.name == "resolve"
                and not test.left.args
            ):
                return {test.type_specifier.name}
    return None


def reference_targets(search_param: SearchParameter) -> List[str]:
    """``SearchParameter.target``, narrowed by the parameter's expression: shared
    definitions list every target of every base (``clinical-patient`` targets
    Patient and Group) while the expression for one base may only allow some
    (``Encounter.subject.where(resolve() is Patient)``)."""
    targets = list(search_param.target or [])
    if not search_param.expression:
        return targets
    try:
        restricted = _resolve_is_types(fhirpath_parse(search_param.expression))
    except FHIRPathSyntaxError:
        return targets
    if restricted is None:
        return targets
    return [t for t in targets if t in restricted]


async def run_chain_resolver_async(resolver: ChainResolver) -> List[str]:
    """Drive a chain resolver with awaitable queries."""
    try:
        query = next(resolver)
        while True:
            query = resolver.send(await query.fetchall())
    except StopIteration as stop:
        return stop.value


@implementer(ISearchContext)
class SearchContext(object):
    """ """

    __slots__ = (
        "resource_types",
        "engine",
        "unrestricted",
        "async_result",
        "definitions",
        "search_params_intersection",
        "warnings",
        "strict",
    )

    definitions: List[ResourceSearchParameterDefinition]

    def __init__(self, engine, resource_type, unrestricted=False, async_result=None):
        """ """
        self.engine = engine
        self.resource_types = [resource_type] if resource_type else []
        self.unrestricted = unrestricted
        # warnings for the Bundle's outcome entry (e.g. ambiguous plain ids)
        self.warnings: List[str] = []
        # strict handling (``Prefer: handling=strict``): ambiguous values are
        # errors instead of warnings
        self.strict = False
        self.async_result = self.engine.__class__.is_async()
        if async_result is not None:
            warn(
                "'async_result' is no longer used, as Engine has that info already. "
                "this parameter will be removed in future release.",
                category=DeprecationWarning,
            )

        self.definitions = self.get_parameters_definition(self.engine.fhir_release)

    def get_parameters_definition(
        self,
        fhir_release: FHIR_VERSION,
    ) -> List[ResourceSearchParameterDefinition]:
        """ """
        fhir_release = FHIR_VERSION.normalize(fhir_release)
        storage = SEARCH_PARAMETERS_STORAGE.get(fhir_release.name)

        if storage.empty():
            spec = FHIRSearchSpecFactory.from_release(fhir_release.name)
            spec.write()

        # if self.resource_types is empty, return the searchparams
        # definitions of the generic "Resource" type.
        return [
            storage.get(resource_type)
            for resource_type in (self.resource_types or ["Resource"])
        ]

    def augment_with_types(self, resource_types: List[str]):
        if len(resource_types) == 0:
            return

        self.resource_types.extend(resource_types)
        self.definitions = self.get_parameters_definition(self.engine.fhir_release)

        self.search_params_intersection = [
            sp for sp in self.definitions[0] if all(sp in d for d in self.definitions)
        ]

    def resolve_path_context(self, search_param: SearchParameter) -> ElementPath:
        """First element path of the parameter (e.g. for sorting)."""
        return self.resolve_path_contexts(search_param)[0]

    def resolve_path_contexts(self, search_param: SearchParameter) -> List[ElementPath]:
        """Element paths the parameter searches on, one per expression branch
        (``Observation.value.ofType(Quantity) | Observation.value.ofType(SampledData)``
        -> ``Observation.valueQuantity``, ``Observation.valueSampledData``)."""
        if search_param.expression is None:
            raise NotImplementedError(
                f"search parameter ``{search_param.code}`` has no expression"
            )
        if search_param.processing_mode == "other":
            # R5: the description defines the matching (e.g. ``_in``, ``near``)
            raise NotImplementedError(
                f"search parameter ``{search_param.code}`` needs special processing"
            )

        if search_param.type == "composite":
            # composites are searched by their components
            raise NotImplementedError

        try:
            dotted_paths = search_param.element_paths()
        except UnsupportedExpression as exc:
            raise NotImplementedError(str(exc))
        paths = self.dotted_paths_to_path_contexts(dotted_paths)
        paths = [self._search_param_type_path(path, search_param) for path in paths]
        for path in paths:
            path.search_param_type = search_param.type
        return paths

    def dotted_paths_to_path_contexts(
        self, dotted_paths: List[str]
    ) -> List[ElementPath]:
        """Element paths of ``dotted_paths``; a choice element without its type
        (``Observation.effective``) stands for all its typed elements. Invalid
        paths are skipped as long as one path is valid."""
        paths: List[ElementPath] = []
        errors: List[Exception] = []
        for dotted_path in dotted_paths:
            try:
                paths.append(self._dotted_path_to_path_context(dotted_path))
                continue
            except ValidationError as exc:
                errors.append(exc)
            for typed_path in self._choice_paths(dotted_path):
                paths.append(self._dotted_path_to_path_context(typed_path))
        if not paths:
            raise errors[0]
        return paths

    def _choice_paths(self, dotted_path: str) -> List[str]:
        """Typed elements of a choice element: ``Observation.effective`` ->
        ``Observation.effectiveDateTime``, ``Observation.effectivePeriod``, ..."""
        if "(" in dotted_path or "[" in dotted_path or "." not in dotted_path:
            return []
        parent_path, name = dotted_path.rsplit(".", 1)
        release = self.engine.fhir_release
        if "." in parent_path:
            context = PathInfoContext.context_from_path(parent_path, release)
            if context is None:
                return []
            model_class = context.type_class.model_class
        else:
            try:
                model_class = lookup_fhir_class(parent_path, release)
            except LookupError:
                return []
        if model_class is None:
            return []
        return [
            f"{parent_path}.{field_name}"
            for field_name, field in model_class.model_fields.items()
            if (field.json_schema_extra or {}).get("one_of_many") == name
        ]

    @staticmethod
    def _search_param_type_path(path: ElementPath, search_param: SearchParameter):
        """``CodeableReference`` (R4B+) is searched on ``.concept`` by token and on
        ``.reference`` by reference parameters."""
        type_info = path.context.get_real_type_class()
        if getattr(type_info, "fhir_type_name", None) and (
            type_info.fhir_type_name() == "CodeableReference"
        ):
            if search_param.type == "token":
                return path / "concept"
            if search_param.type == "reference":
                return path / "reference"
        return path

    def normalize_param(
        self, param_name, raw_value
    ) -> List[Tuple[ElementPath, str, Optional[str]]]:
        """ """
        try:
            parts = param_name.split(":")
            param_name_ = parts[0]
            modifier_ = parts[1]
        except IndexError:
            modifier_ = None

        normalized_params: List[Tuple[ElementPath, str, Optional[str]]] = []
        search_params_def = self._get_search_param_definitions(param_name_)

        for sp in search_params_def:
            if modifier_ is not None:
                self.validate_modifier(sp, modifier_)

            if sp.type == "composite":
                normalized_params.extend(
                    self._normalize_composite_param(
                        raw_value if isinstance(raw_value, list) else [raw_value],
                        param_def=sp,
                        modifier=modifier_,
                    )
                )
                continue

            sp_raw_value = raw_value
            if isinstance(sp_raw_value, list):
                if len(sp_raw_value) == 0:
                    sp_raw_value = None
                elif len(sp_raw_value) == 1:
                    sp_raw_value = sp_raw_value[0]

            values: List = self.normalize_param_value(sp_raw_value, sp)
            if modifier_ and self.is_type_modifier(sp, modifier_):
                # ``subject:Patient=23`` ≡ ``subject=Patient/23``
                values = map_normalized_values(
                    values,
                    lambda leaf, t=modifier_: (
                        leaf[0],
                        typed_reference_value(t, leaf[1]),
                    ),
                )
                modifier_ = None

            if len(values) == 0:
                # empty parameters are not considered an error, they should be ignored
                continue
            if len(values) == 1:
                param_value_ = values[0]
            else:
                param_value_ = values

            Search.validate_normalized_value(param_name_, param_value_, modifier_)
            presence = (
                computed_presence_path(sp.expression)
                if sp.expression and sp.type == "token"
                else None
            )
            if presence is not None:
                normalized_params.extend(
                    self._normalize_presence_param(sp, presence, values, modifier_)
                )
                continue
            paths = self.resolve_path_contexts(sp)
            entries = [
                (
                    path,
                    self.path_param_value(sp, path, param_value_, modifier_),
                    modifier_,
                )
                for path in paths
            ]
            if len(entries) == 1:
                normalized_params.append(entries[0])
            else:
                # the parameter matches when any of its paths matches
                normalized_params.append(AnyOf(entries))
        return normalized_params

    def _normalize_presence_param(self, search_param, dotted_path, values, modifier):
        """Entries of a computed boolean parameter (``deceased``): one
        ``ComputedPresence`` per value, OR lists as ``AnyOf``."""
        paths = self.dotted_paths_to_path_contexts([dotted_path])
        entries: List = []

        def add(value):
            if isinstance(value, list):
                # AND: each value is an entry
                for item in value:
                    add(item)
                return
            _, raw = value
            if isinstance(raw, list):
                entries.append(
                    AnyOf(
                        ComputedPresence(search_param.code, paths, leaf, modifier)
                        for leaf in raw
                    )
                )
            else:
                entries.append(
                    ComputedPresence(search_param.code, paths, value, modifier)
                )

        add(values)
        return entries

    def path_param_value(
        self, search_param: SearchParameter, path: ElementPath, value, modifier
    ):
        """The value as searched on ``path``: for a reference parameter a plain id
        becomes ``Type/id`` for each type the path may point to
        (``where(resolve() is X)`` restricts it to ``X``). A plain id that may
        point to several types is ambiguous: a warning, or an error with strict
        handling."""
        if search_param.type != "reference" or modifier is not None:
            return value
        if path._where is not None and path._where.type == WhereConstraintType.T2:
            types = [path._where.value]
        else:
            types = [t for t in reference_targets(search_param) if t != "Resource"]

        def leaf_value(leaf):
            if len(types) > 1 and plain_reference_id(leaf[1]):
                message = (
                    f"Reference ``{search_param.code}={leaf[1]}`` is ambiguous: "
                    f"the id may be of a {', '.join(types)}; it is searched as all."
                )
                if self.strict:
                    raise ValidationError(message)
                if message not in self.warnings:
                    self.warnings.append(message)
            return typed_reference_leaf(types, leaf)

        return map_normalized_values(value, leaf_value)

    @staticmethod
    def is_type_modifier(search_param: SearchParameter, modifier: str) -> bool:
        """``[type]`` modifier of a reference parameter (``subject:Patient``)."""
        if search_param.type != "reference" or not modifier[:1].isupper():
            return False
        targets = search_param.target or []
        return not targets or "Resource" in targets or modifier in targets

    def validate_modifier(self, search_param: SearchParameter, modifier: str):
        """Unsupported modifiers SHALL be rejected (unlike unknown parameters),
        because a modifier changes the meaning of the test."""
        code = search_param.code
        if search_param.type == "composite":
            raise ValidationError(
                f"Composite search parameter ``{code}`` does not take modifiers "
                f"(got ``:{modifier}``)."
            )
        if self.is_type_modifier(search_param, modifier):
            return
        if search_param.type == "reference" and modifier[:1].isupper():
            raise ValidationError(
                f"``{modifier}`` is not a target type of reference search "
                f"parameter ``{code}`` (targets: {', '.join(search_param.target)})."
            )
        supported = SUPPORTED_MODIFIERS.get(search_param.type, set())
        if modifier not in supported:
            raise ValidationError(
                f"Modifier ``:{modifier}`` is not supported for search parameter "
                f"``{code}`` of type ``{search_param.type}``."
            )
        since = MODIFIER_SINCE.get(modifier)
        release = FHIR_VERSION.normalize(self.engine.fhir_release)
        if since is not None and RELEASE_ORDER.index(release) < RELEASE_ORDER.index(
            since
        ):
            raise ValidationError(
                f"Modifier ``:{modifier}`` is not supported in FHIR {release.name} "
                f"(search parameter ``{code}``)."
            )
        # a definition that lists its modifiers allows only those
        allowed = {
            "of-type" if m == "ofType" else m for m in (search_param.modifier or [])
        }
        if allowed and "missing" in allowed:
            allowed.add("exists")
        if allowed and modifier not in allowed:
            raise ValidationError(
                f"Modifier ``:{modifier}`` is not allowed by the definition of "
                f"search parameter ``{code}``."
            )

    def normalize_param_value(
        self, raw_value: Union[List, str], search_param: SearchParameter
    ):
        normalized_values: List[Any] = []
        if not raw_value:
            return []

        elif isinstance(raw_value, list):
            bucket: List[str] = list()
            for rv in raw_value:
                bucket.extend(self.normalize_param_value(rv, search_param))
            if len(bucket) == 1:
                normalized_values.append(bucket[0])
            else:
                normalized_values.append(bucket)

        else:
            validate_escapes(raw_value)
            # the values keep their escapes until the leaf terms are built
            # (``create_term``), so that ``|`` and ``$`` can still be split on
            value_parts = split_escaped(raw_value, ",")
            bucket_ = list()
            for val_ in value_parts:
                comparison_operator = "eq"
                for prefix in search_param_prefixes:
                    if val_.startswith(prefix) and search_param.support_prefix():
                        comparison_operator = prefix
                        val_ = val_[2:]
                        break
                bucket_.append((comparison_operator, val_))
            if len(bucket_) == 1:
                normalized_values.append(bucket_[0])
            else:
                normalized_values.append((None, bucket_))

        return normalized_values

    def _get_search_param_definitions(self, param_name) -> List[SearchParameter]:
        """ """
        params_def = []
        for definition in self.definitions:
            search_param = getattr(definition, param_name, None)
            if search_param is None:
                if param_name in ("_format", "_pretty"):
                    continue
                raise ValidationError(
                    "No search definition is available for search parameter "
                    f"``{param_name}`` on Resource ``{definition.resource_type}``."
                )
            params_def.append(search_param)
        return params_def

    def _dotted_path_to_path_context(self, dotted_path):
        """ """
        if len(dotted_path.split(".")) == 1:
            raise ValidationError("Invalid dotted path ´{0}´".format(dotted_path))

        path_ = ElementPath.from_el_path(dotted_path)
        path_.finalize(self.engine)
        return path_

    def _normalize_composite_param(self, raw_value, param_def, modifier) -> List:
        """One entry per value (repeats are ANDed); a value is an OR list of
        ``$``-separated tuples (``code-value-quantity=a$1,b$2``), each matched
        within one element of the composite's base path (``CompositeTuple``)."""
        entries: List = []
        for raw in raw_value or []:
            if not raw:
                # empty values are ignored
                continue
            validate_escapes(raw)
            alternatives = [
                self._composite_tuple(param_def, raw_tuple)
                for raw_tuple in split_escaped(raw, ",")
            ]
            entries.append(
                alternatives[0] if len(alternatives) == 1 else AnyOf(alternatives)
            )
        return entries

    def _composite_tuple(self, param_def, raw_tuple):
        value_parts = split_escaped(raw_tuple, "$")
        if len(value_parts) != len(param_def.component):
            raise ValidationError(
                f"Composite search param {param_def.code} expects "
                f"{len(param_def.component)} values separated by a '$', "
                f"got {len(value_parts)}."
            )
        try:
            base_paths = param_def.element_paths()
        except UnsupportedExpression as exc:
            raise NotImplementedError(str(exc))

        tuples = []
        for base_path in base_paths:
            components = [
                self.parse_composite_parameter_component(
                    component, value_part, param_def, base_path
                )
                for component, value_part in zip(param_def.component, value_parts)
            ]
            group_path = None
            if "." in base_path:
                group_path = self._dotted_path_to_path_context(base_path)
            tuples.append(CompositeTuple(components, base_path=group_path))
        return tuples[0] if len(tuples) == 1 else AnyOf(tuples)

    def parse_composite_parameter_component(
        self, component, raw_value, param_def, base_path
    ):
        try:
            dotted_paths = component_paths(base_path, component["expression"])
        except UnsupportedExpression as exc:
            raise NotImplementedError(str(exc))

        # parse the value with the component's own type (prefixes for number,
        # date and quantity components)
        component_param = param_def.clone()
        component_param.type = component.get("_type") or param_def.type
        component_param_value = self.normalize_param_value(raw_value, component_param)
        if len(component_param_value) == 1:
            component_param_value = component_param_value[0]

        paths = self.dotted_paths_to_path_contexts(dotted_paths)
        for path in paths:
            path.search_param_type = component_param.type
        result = [(path, component_param_value, None) for path in paths]
        if len(result) == 1:
            return result[0]
        return AnyOf(result)


_PROFILES: Dict[str, Dict[str, Any]] = {}
_SUBSETTING: Dict[Tuple[str, str], Dict[str, Any]] = {}
# elements every resource may carry that change its meaning
BASE_MODIFIER_ELEMENTS = ("implicitRules", "modifierExtension")


def _resource_profiles(release: FHIR_VERSION) -> Dict[str, Any]:
    """StructureDefinitions of the resources of a release, by type."""
    release = FHIR_VERSION.normalize(release)
    if release.name not in _PROFILES:
        import json

        from fhirpath.search.fhirspec import SPEC_JSON_DIR, ensure_spec_jsons

        ensure_spec_jsons(release)
        path = (
            SPEC_JSON_DIR / release.name / release.value / "profiles-resources.min.json"
        )
        with open(str(path), encoding="utf-8") as fp:
            bundle = json.load(fp)
        _PROFILES[release.name] = {
            entry["resource"]["type"]: entry["resource"]
            for entry in bundle.get("entry", [])
            if entry["resource"].get("kind") == "resource"
            and entry["resource"].get("derivation", "specialization") == "specialization"
        }
    return _PROFILES[release.name]


def subsetting_elements(resource_type: str, release: FHIR_VERSION) -> Dict[str, Any]:
    """``mandatory`` and ``modifier`` top-level elements of a resource type
    (which ``_elements`` SHOULD always return) and ``names``: the JSON names of
    each element (a choice element has one per type)."""
    release = FHIR_VERSION.normalize(release)
    key = (release.name, resource_type)
    if key in _SUBSETTING:
        return _SUBSETTING[key]
    mandatory: List[str] = []
    modifier: List[str] = list(BASE_MODIFIER_ELEMENTS)
    profile = _resource_profiles(release).get(resource_type, {})
    elements = profile.get("snapshot", profile.get("differential", {})).get(
        "element", []
    )
    for element in elements:
        parts = element.get("path", "").split(".")
        if len(parts) != 2:
            continue
        name = parts[1].replace("[x]", "")
        if element.get("min", 0) > 0 and name not in mandatory:
            mandatory.append(name)
        if element.get("isModifier") and name not in modifier:
            modifier.append(name)
    names: Dict[str, List[str]] = {}
    try:
        model_class = lookup_fhir_class(resource_type, release)
    except LookupError:
        model_class = None
    for field in (model_class.model_fields.values() if model_class else []):
        extra = field.json_schema_extra or {}
        if not extra.get("element_property"):
            continue
        names.setdefault(field.alias, []).append(field.alias)
        if extra.get("one_of_many"):
            names.setdefault(extra["one_of_many"], []).append(field.alias)
    _SUBSETTING[key] = {"mandatory": mandatory, "modifier": modifier, "names": names}
    return _SUBSETTING[key]


def subset_resource(resource: Dict[str, Any], names: List[str]) -> Dict[str, Any]:
    """A copy of a resource with only ``names`` (and ``resourceType``)."""
    return {
        key: value
        for key, value in resource.items()
        if key == "resourceType" or key in names
    }


def tag_subsetted(resource):
    """Add the ``SUBSETTED`` tag to a resource (dict)."""
    if not isinstance(resource, dict):
        return
    meta = resource.setdefault("meta", {})
    tags = meta.setdefault("tag", [])
    if not any(
        t.get("code") == SUBSETTED_TAG["code"] and t.get("system") == SUBSETTED_TAG["system"]
        for t in tags
    ):
        tags.append(dict(SUBSETTED_TAG))


# primitive elements a complex element is sorted on (``:text``: its text)
SORT_LEAVES: Dict[str, Tuple[str, ...]] = {
    "HumanName": ("family", "given"),
    "Address": ("text", "city", "country"),
    "CodeableConcept": ("coding.code",),
    "Coding": ("code",),
    "Identifier": ("value",),
    "Reference": ("reference",),
    "ContactPoint": ("value",),
    "Period": ("start",),
    "Range": ("low.value",),
    "Timing": ("event",),
    "Attachment": ("title",),
    "Money": ("value",),
    **{name: ("value",) for name in QUANTITY_TYPES},
}
SORT_TEXT_LEAVES: Dict[str, Tuple[str, ...]] = {
    "CodeableConcept": ("text", "coding.display"),
    "Coding": ("display",),
    "Reference": ("display",),
    "Identifier": ("type.text",),
}


class IncludeSpec(NamedTuple):
    """One ``_include`` / ``_revinclude``: follow ``ref_param`` of
    ``source_type`` (``*``: every reference parameter)."""

    kind: str
    source_type: str
    code: str
    ref_param: Optional[SearchParameter]
    target_type: Optional[str]
    iterate: bool


def row_key(row) -> Tuple[str, str]:
    """``(resource type, id)`` of a result row."""
    resource = row[0]
    if isinstance(resource, dict):
        return resource.get("resourceType"), resource.get("id")
    return resource.get_resource_type(), resource.id


class CompositeTuple(list):
    """The components (normalized entries) of one composite value, which must
    match within the same element at ``base_path`` (``None``: the resource)."""

    def __init__(self, components, base_path=None):
        super().__init__(components)
        self.base_path = base_path


class ComputedPresence:
    """Normalized value of a computed boolean parameter such as Patient
    ``deceased`` (``Patient.deceased.exists() and Patient.deceased != false``):
    the typed choice ``paths`` of the element."""

    def __init__(self, code, paths, value, modifier):
        self.code = code
        self.paths = paths
        self.value = value
        self.modifier = modifier


class AnyOf(list):
    """Normalized ``(path, value, modifier)`` entries of which any must match:
    a search parameter with several paths."""


@implementer(ISearch)
class Search(object):
    """ """

    def __init__(
        self,
        context: SearchContext,
        query_string=None,
        params=None,
        handling: str = HANDLING_LENIENT,
    ):
        """``handling``: ``lenient`` (default) ignores unknown search parameters,
        ``strict`` rejects them (``Prefer: handling=strict``, see
        ``handling_from_prefer``)."""
        # validate first
        Search.validate_params(context, query_string, params)
        if handling not in (HANDLING_LENIENT, HANDLING_STRICT):
            raise ValidationError(
                f"handling must be ``{HANDLING_LENIENT}`` or ``{HANDLING_STRICT}``, "
                f"got ``{handling}``."
            )
        self.handling = handling

        self.context = ISearchContext(context)
        all_params = None
        if isinstance(params, MultiDict):
            all_params = params
        elif isinstance(query_string, str):
            all_params = Search.parse_query_string(query_string, False)
        elif isinstance(params, (tuple, list)):
            all_params = MultiDict(params)
        elif isinstance(params, dict):
            all_params = MultiDict(params.items())
        elif isinstance(params, MultiDictProxy):
            all_params = params.copy()

        self.result_params: Dict[str, str] = dict()
        self.search_params = None

        self.reverse_chaining_results: Optional[Dict[str, Set[str]]] = None
        # chained parameters ("subject:Patient.name=peter"), as (name, value) pairs
        self.chain_params: List[Tuple[str, str]] = []
        # resolved chains: (reference search param, matching "Type/id" references)
        self.chained_references: List[Tuple[str, List[str]]] = []
        self.main_query = None
        self.include_queries = None

        # what the self link reports: every parameter with a value (empty
        # values are ignored), minus the unknown parameters that are ignored
        self.applied_params = MultiDict(
            (k, v) for k, v in (all_params or {}).items() if v
        )
        # unknown search parameters left out of the search (lenient handling)
        self.ignored_params: List[str] = []
        # (issue code, message) warnings for the Bundle's outcome entry
        self.warnings: List[Tuple[str, str]] = []
        # resolved ``reference:below`` / ``:above`` parameters
        self.hierarchy_references: Dict[str, List[str]] = {}
        self.context.strict = self.handling == HANDLING_STRICT
        self.prepare_params(all_params)

        additional_resource_types = self.result_params.get("_type")
        if additional_resource_types:
            self.context.augment_with_types(additional_resource_types)

        if self.handling == HANDLING_LENIENT:
            self.drop_unknown_params()
        self.check_contained()

    def drop_unknown_params(self):
        """Unknown search parameters SHOULD be ignored unless strict handling is
        asked for: they are left out of the search and of the ``self`` link. A
        parameter defined for only some of the searched types is still an error.
        """
        known = MultiDict()
        for name, value in self.search_params.items():
            code = name.split(":")[0]
            if code in ("_format", "_pretty") or any(
                getattr(definition, code, None) is not None
                for definition in self.context.definitions
            ):
                known.add(name, value)
            elif name not in self.ignored_params:
                logger.info(f"unknown search parameter ``{name}`` is ignored")
                self.ignored_params.append(name)
        if not self.ignored_params:
            return
        self.search_params = MultiDictProxy(known)
        self.applied_params = MultiDict(
            (k, v)
            for k, v in self.applied_params.items()
            if k not in self.ignored_params
        )

    def check_contained(self):
        """Contained resources are not indexed by themselves, so they cannot be
        searched (``_contained=true|both``): with lenient handling the
        parameters are ignored (left out of the self link, with a warning)."""
        contained = self.result_params.get("_contained")
        if contained not in ("true", "both"):
            return
        message = (
            f"_contained={contained} is not supported: contained resources are "
            "not searched."
        )
        if self.handling == HANDLING_STRICT:
            raise ValidationError(message)
        self.warn(message, "not-supported")
        for name in ("_contained", "_containedType"):
            self.result_params.pop(name, None)
        self.applied_params = MultiDict(
            (k, v)
            for k, v in self.applied_params.items()
            if k not in ("_contained", "_containedType")
        )

    @staticmethod
    def validate_params(context, query_string, params):
        """ """
        if not ISearchContext.providedBy(context):
            raise ValidationError(
                ":context must be implemented "
                "fhirpath.interfaces.ISearchContext interface"
            )

        if query_string and params:
            raise ValidationError(
                "Only value from one of arguments "
                "(´query_string´, ´params´) is accepted"
            )

    @staticmethod
    def parse_query_string(query_string, allow_none=False):
        """
        param:request
        param:allow_none
        """
        params = MultiDict()

        for q in query_string.split("&"):
            parts = q.split("=")
            param_name = unquote_plus(parts[0])
            try:
                value = parts[1] and unquote_plus(parts[1]) or None
            except IndexError:
                if not allow_none:
                    continue
                value = None

            params.add(param_name, value)

        return params

    @classmethod
    def from_query_string(cls, query_string):
        """ """

    @classmethod
    def from_params(cls, context, params):
        """ """
        return cls(context, params=params)

    def prepare_params(self, all_params):
        """making search, sort, limit, params
        Result Parameters
        ~~~~~~~~~~~~~~~~
        _sort
        _count
        _include
        _revinclude
        _summary
        _total
        _elements
        _contained
        _containedType
        """
        if all_params is None:
            self.search_params = MultiDict()
            return

        _sort = all_params.popall("_sort", [])
        if len(_sort) > 0:
            self.result_params["_sort"] = ",".join(_sort)

        _count = self._single_param(all_params, "_count")
        if _count is not None:
            count = self._whole_number("_count", _count)
            self.result_params["_count"] = count
            if count == 0:
                # _count=0 is _summary=count: the total only
                all_params.popall("_summary", None)
                all_params.add("_summary", "count")

        page = self._single_param(all_params, "page")
        if page is not None:
            self.result_params["page"] = max(self._whole_number("page", page), 1)

        _maxresults = self._single_param(all_params, "_maxresults")
        if _maxresults is not None:
            self.result_params["_maxresults"] = self._whole_number(
                "_maxresults", _maxresults
            )

        _total = self._single_param(all_params, "_total")
        if _total is not None:
            if _total not in TOTAL_VALUES:
                raise ValidationError(
                    f"'_total' must be one of {', '.join(TOTAL_VALUES)}, "
                    f"got '{_total}'."
                )
            self.result_params["_total"] = _total

        _score = self._single_param(all_params, "_score")
        if _score is not None:
            if _score not in ("true", "false"):
                raise ValidationError(f"'_score' must be true or false, got '{_score}'.")
            self.result_params["_score"] = _score == "true"

        _type = all_params.popone("_type", None)
        if _type:
            self.result_params["_type"] = _type.split(",")

        _summary = self._single_param(all_params, "_summary")
        if _summary is not None:
            if _summary not in SUMMARY_VALUES:
                raise ValidationError(
                    f"'_summary' must be one of {', '.join(SUMMARY_VALUES)}, "
                    f"got '{_summary}'."
                )
            self.result_params["_summary"] = _summary

        _graph = self._single_param(all_params, "_graph")
        if _graph is not None:
            self.result_params["_graph"] = _graph

        for name in ("_text", "_content", "_filter", "_query", "_list"):
            values = [v for v in all_params.popall(name, []) if v]
            if values:
                self.result_params[name] = values

        # (value, iterate) pairs; STU3 calls :iterate :recurse
        for kind in ("_include", "_revinclude"):
            specs = [(v, False) for v in all_params.popall(kind, []) if v]
            for modifier in ("iterate", "recurse"):
                specs.extend(
                    (v, True) for v in all_params.popall(f"{kind}:{modifier}", []) if v
                )
            if specs:
                self.result_params[kind] = specs

        _has = [(k, v) for k, v in all_params.items() if k.startswith("_has:")]
        # empty values are ignored, like for any other search parameter
        if any(v for _, v in _has):
            self.result_params["_has"] = [(k, v) for k, v in _has if v]
        [all_params.popall(k, None) for k, _ in _has]


        _elements = self._single_param(all_params, "_elements")
        if _elements:
            self.result_params["_elements"] = [
                e.strip() for e in _elements.split(",") if e.strip()
            ]

        _contained = self._single_param(all_params, "_contained")
        if _contained is not None:
            if _contained not in ("false", "true", "both"):
                raise ValidationError(
                    f"'_contained' must be false, true or both, got '{_contained}'."
                )
            self.result_params["_contained"] = _contained

        _containedType = self._single_param(all_params, "_containedType")
        if _containedType is not None:
            if _containedType not in ("container", "contained"):
                raise ValidationError(
                    "'_containedType' must be container or contained, "
                    f"got '{_containedType}'."
                )
            self.result_params["_containedType"] = _containedType

        if self.result_params.get("_summary") == "text" and (
            self.result_params.get("_include") or self.result_params.get("_revinclude")
        ):
            raise ValidationError(
                "_include and _revinclude cannot be combined with _summary=text."
            )

        # chained parameters: every remaining name containing a "." -
        # empty values are ignored, like for any other search parameter
        chained = [(k, v) for k, v in all_params.items() if "." in k]
        self.chain_params = [(k, v) for k, v in chained if v]
        [all_params.popall(k, None) for k, _ in chained]

        self.search_params = MultiDictProxy(all_params)

    @staticmethod
    def _single_param(all_params, name) -> Optional[str]:
        """The value of a result parameter that may appear once (empty values
        are ignored)."""
        values = [v for v in all_params.popall(name, []) if v]
        if len(values) > 1:
            raise ValidationError(f"'{name}' cannot be multiple!")
        return values[0] if values else None

    @staticmethod
    def _whole_number(name, value) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = -1
        if number < 0:
            raise ValidationError(f"'{name}' must be a whole number, got '{value}'.")
        return number

    def build(self) -> QueryResult:
        """Create QueryBuilder from search query string"""
        builder = Q_(self.context.resource_types, self.context.engine)

        builder = self.attach_where_terms(builder)
        builder = self.attach_elements_terms(builder)
        builder = self.attach_sort_terms(builder)
        builder = self.attach_summary_terms(builder)
        builder = self.attach_limit_terms(builder)
        if self.result_params.get("_total") == "accurate":
            builder = builder.option(track_total_hits=True)

        # _has and chained parameters: restrictions resolved beforehand
        builder = self.apply_resolved_terms(builder)

        result: QueryResult = builder(unrestricted=self.context.unrestricted)

        return result

    def reverse_chain(self, param_name: str, value: str) -> ChainResolver:
        """Resolve a top-level reverse chain, e.g. ``_has:Observation:patient:code``,
        nested (``_has:Observation:patient:_has:AuditEvent:entity:agent``) or
        followed by a chain (``_has:Observation:subject:performer.name``).

        Returns the "Type/id" references of the resources of the search context
        that are referred to by matching sources. With several resource types in
        the context, the types the reverse chain cannot refer to are skipped.
        """
        if not self.context.resource_types:
            raise ValidationError(
                f"'{param_name}' needs a resource type: search on a type or use _type"
            )
        links = param_name.split(".")
        applicable = [
            resource_type
            for resource_type in self.context.resource_types
            if self._has_link_targets(links[0], resource_type)
        ]
        if not applicable:
            # resolving against the first type raises the reason
            # (unknown or non-reference parameter, invalid target...)
            applicable = self.context.resource_types[:1]

        references: List[str] = []
        for resource_type in applicable:
            context = SearchContext(
                self.context.engine,
                resource_type,
                unrestricted=self.context.unrestricted,
            )
            references.extend(
                (yield from self._resolve_has_link(context, links, value))
            )
        return references

    def reverse_chains(
        self,
    ) -> Generator[QueryResult, EngineResult, Dict[str, Set[str]]]:
        """Resolve every top-level ``_has`` parameter; they are ANDed: the result
        maps each resource type to the ids that satisfy all of them (empty when
        none can match)."""
        results: Optional[Dict[str, Set[str]]] = None
        for param_name, value in self.result_params.get("_has", []):
            references = yield from self.reverse_chain(param_name, value)
            found: Dict[str, Set[str]] = {}
            for reference in references:
                resource_type, id_ = reference.split("/", 1)
                found.setdefault(resource_type, set()).add(id_)
            if results is None:
                results = found
            else:
                results = {
                    resource_type: ids & found[resource_type]
                    for resource_type, ids in results.items()
                    if ids & found.get(resource_type, set())
                }
            if not results:
                return {}
        return results or {}

    @staticmethod
    def parse_chain_link(link: str) -> Tuple[str, Optional[str]]:
        """Split one link of a chain (``subject`` or ``subject:Patient``)
        into the reference search parameter name and the optional target type."""
        parts = link.split(":")
        if len(parts) > 2 or not all(parts):
            raise ValidationError(f"bad chained search parameter link '{link}'")
        return parts[0], parts[1] if len(parts) == 2 else None

    def chain(self, param_name: str, value: str) -> ChainResolver:
        """Resolve a chained parameter, e.g. ``subject:Patient.name=peter``.

        Returns the "Type/id" references that the first reference search parameter
        (``subject``) must point to; each chain is resolved independently (FHIR R5
        search §3.2.1.6.5), the main query then ORs over these references.
        """
        references = yield from self._resolve_chain_link(
            self.context, param_name.split("."), value
        )
        return references

    def _resolve_chain_link(
        self, context: SearchContext, links: List[str], value: str
    ) -> ChainResolver:
        """Resolve ``links[0]`` (a reference search parameter of ``context``) against
        the rest of the chain, returning the matching target references."""
        ref_name, target_type = self.parse_chain_link(links[0])
        next_link = links[1]
        next_name = next_link.split(":")[0]
        if not next_name:
            raise ValidationError(f"bad chained search parameter '{'.'.join(links)}'")
        context_name = ",".join(context.resource_types) or "Resource"

        targets: List[str] = []
        for ref_param in context._get_search_param_definitions(ref_name):
            if ref_param.type != "reference":
                raise ValidationError(
                    f"chained search parameter {context_name}.{ref_name} "
                    f"must be of type 'reference', got {ref_param.type}"
                )
            targets.extend(t for t in reference_targets(ref_param) if t not in targets)

        if target_type is not None:
            if target_type not in targets:
                raise ValidationError(
                    f"the search param {context_name}.{ref_name} may refer"
                    f" to {', '.join(targets)}, not to {target_type}"
                )
            targets = [target_type]
        elif next_name == "_has":
            # follow every target type that the reverse chain can point back to
            candidates = targets
            targets = [t for t in targets if self._has_link_targets(next_link, t)]
            if not targets:
                raise ValidationError(
                    f"reverse chain '{next_link}' cannot refer to any target "
                    f"of ``{context_name}.{ref_name}`` ({', '.join(candidates)})"
                )
        else:
            # without an explicit type, follow every target type that defines
            # the next search parameter
            targets = [t for t in targets if self._defines_search_param(t, next_name)]
            if not targets:
                raise ValidationError(
                    "No search definition is available for search parameter "
                    f"``{next_name}`` on any target of ``{context_name}.{ref_name}``."
                )

        references: List[str] = []
        for resource_type in targets:
            target_context = SearchContext(
                context.engine, resource_type, unrestricted=context.unrestricted
            )
            terms = yield from self._param_terms(target_context, links[1:], value)
            if not terms:
                continue

            builder = Q_(resource_type, context.engine).where(*terms)
            result = yield builder(unrestricted=context.unrestricted)
            references.extend(
                f"{resource_type}/{id_}"
                for id_ in result.extract_ids().get(resource_type, [])
            )
        return references

    def _param_terms(
        self, context: SearchContext, links: List[str], value: str
    ) -> Generator[QueryResult, EngineResult, Optional[List]]:
        """Terms selecting the resources of ``context`` that match the parameter
        path ``links`` (a plain parameter, a chain or a reverse chain) with
        ``value``. ``None`` means that no resource can match."""
        first_link = links[0]
        if first_link.startswith("_has:"):
            references = yield from self._resolve_has_link(context, links, value)
            if not references:
                return None
            param_name, raw_value = "_id", ",".join(
                reference.split("/", 1)[1] for reference in references
            )
        elif len(links) > 1:
            references = yield from self._resolve_chain_link(context, links, value)
            if not references:
                return None
            param_name = self.parse_chain_link(first_link)[0]
            raw_value = ",".join(references)
        else:
            param_name, raw_value = first_link, value

        terms: List = []
        for normalized_data in context.normalize_param(param_name, [raw_value]):
            self.add_term(normalized_data, terms)
        return terms

    @staticmethod
    def parse_has_link(link: str) -> Tuple[str, str, str]:
        """``_has:Observation:patient:code`` -> ("Observation", "patient", "code").

        The last part keeps any modifier or nested reverse chain
        (``_has:Observation:patient:_has:AuditEvent:entity:agent``)."""
        parts = link.split(":")
        if len(parts) < 4 or parts[0] != "_has" or not all(parts[1:4]):
            raise ValidationError(
                f"bad _has param '{link}', "
                "should be _has:Resource:ref_search_param:value_search_param=value"
            )
        return parts[1], parts[2], ":".join(parts[3:])

    def _has_reference_param(
        self, source_context: SearchContext, ref_name: str, resource_type: str
    ) -> SearchParameter:
        """The reference parameter of a reverse chain, which must be able to point
        to ``resource_type``."""
        source_type = source_context.resource_types[0]
        ref_param = source_context._get_search_param_definitions(ref_name)[0]
        if ref_param.type != "reference":
            raise ValidationError(
                f"search parameter {source_type}.{ref_name} "
                f"must be of type 'reference', got {ref_param.type}"
            )
        targets = reference_targets(ref_param)
        if resource_type not in targets:
            raise ValidationError(
                f"invalid reference {source_type}.{ref_name} "
                f"({','.join(targets)}) in the current search context "
                f"({resource_type})"
            )
        return ref_param

    def _has_link_targets(self, link: str, resource_type: str) -> bool:
        """Whether the reverse chain ``link`` can refer to ``resource_type``."""
        source_type, ref_name, _ = self.parse_has_link(link)
        try:
            source_context = SearchContext(self.context.engine, source_type)
            self._has_reference_param(source_context, ref_name, resource_type)
        except (ValidationError, KeyError, AttributeError):
            return False
        return True

    def _resolve_has_link(
        self, context: SearchContext, links: List[str], value: str
    ) -> ChainResolver:
        """Resolve a reverse chain on ``context`` (e.g. ``_has:Group:member:_id``,
        possibly followed by more chain links), returning the "Type/id" references
        of the ``context`` resources that are referred to by matching sources."""
        (resource_type,) = context.resource_types
        source_type, ref_name, value_link = self.parse_has_link(links[0])
        source_context = SearchContext(
            context.engine, source_type, unrestricted=context.unrestricted
        )
        ref_param = self._has_reference_param(source_context, ref_name, resource_type)

        terms = yield from self._param_terms(
            source_context, [value_link, *links[1:]], value
        )
        if not terms:
            return []

        builder = Q_(source_type, context.engine).where(*terms)
        result = yield builder(unrestricted=context.unrestricted)
        ids = result.extract_references(ref_param).get(resource_type, [])
        return [f"{resource_type}/{id_}" for id_ in dict.fromkeys(ids)]

    def _defines_search_param(self, resource_type: str, param_name: str) -> bool:
        try:
            context = SearchContext(self.context.engine, resource_type)
        except Exception:  # unknown resource type in the definitions storage
            return False
        return param_name in context.definitions[0]

    # ---------------------------------------------- hierarchies (:above/:below)

    def hierarchy_params(self) -> List[str]:
        """Reference parameters with ``:below`` / ``:above``: a search over the
        hierarchy formed by a circular reference (``Location.partOf``)."""
        names = []
        for name in set(self.search_params):
            parts = name.split(":")
            if len(parts) != 2 or parts[1] not in ("below", "above"):
                continue
            definitions = [
                getattr(d, parts[0], None) for d in self.context.definitions
            ]
            if any(d is not None and d.type == "reference" for d in definitions):
                names.append(name)
        return sorted(names)

    def hierarchy_param(self, resource_type: str) -> Optional[SearchParameter]:
        """The reference parameter of ``resource_type`` that points to its
        parent of the same type (``partof``)."""
        candidates = [
            sp
            for sp in self.reference_params(resource_type)
            if resource_type in reference_targets(sp)
            and (
                sp.code in ("partof", "part-of")
                or (sp.expression or "").endswith(".partOf")
            )
        ]
        return candidates[0] if candidates else None

    def resolve_hierarchy(self, name: str) -> ChainResolver:
        """References of the hierarchy below (or above) each value: the value
        itself and every descendant (ancestor), at any depth."""
        code, modifier = name.split(":")
        references: List[str] = []
        for value in self.search_params.getall(name):
            validate_escapes(value)
            for leaf in split_escaped(value, ","):
                leaf = unescape_value(leaf)
                for sp in self.context._get_search_param_definitions(code):
                    targets = [t for t in reference_targets(sp) if t != "Resource"]
                    match = local_reference.match(leaf)
                    if match is not None:
                        roots = [(match.group("type"), match.group("id"))]
                    elif plain_reference_id(leaf):
                        roots = [
                            (t, leaf) for t in targets if self.hierarchy_param(t)
                        ]
                    else:
                        raise ValidationError(
                            f"``{name}`` expects ``[Type/]id``, got ``{leaf}``."
                        )
                    for resource_type, id_ in roots:
                        ids = yield from self._hierarchy_closure(
                            resource_type, id_, modifier, name
                        )
                        references.extend(
                            f"{resource_type}/{i}"
                            for i in ids
                            if f"{resource_type}/{i}" not in references
                        )
        return references

    def _hierarchy_closure(self, resource_type, id_, modifier, name) -> ChainResolver:
        parent_param = self.hierarchy_param(resource_type)
        if parent_param is None:
            raise ValidationError(
                f"``{name}``: {resource_type} references do not form a hierarchy."
            )
        context = SearchContext(
            self.context.engine, resource_type, unrestricted=self.context.unrestricted
        )
        collected = [id_]
        frontier = [id_]
        for _ in range(HIERARCHY_MAX_DEPTH):
            terms: List = []
            if modifier == "below":
                refs = ",".join(f"{resource_type}/{i}" for i in frontier)
                normalized = context.normalize_param(parent_param.code, [refs])
            else:
                normalized = context.normalize_param("_id", [",".join(frontier)])
            self.add_term(normalized, terms)
            result = yield Q_(resource_type, self.context.engine).where(*terms)(
                unrestricted=self.context.unrestricted
            )
            if modifier == "below":
                found = result.extract_ids().get(resource_type, [])
            else:
                found = result.extract_references(parent_param).get(resource_type, [])
            frontier = [i for i in dict.fromkeys(found) if i not in collected]
            if not frontier:
                break
            collected.extend(frontier)
        return collected

    def chain_reference_name(self, param_name: str) -> str:
        """``subject:Patient.name`` -> ``subject``"""
        return self.parse_chain_link(param_name.split(".")[0])[0]

    def empty_response(self, as_json):
        return self.response(
            EngineResult(EngineResultHeader(total=0), EngineResultBody()), [], as_json
        )

    # ------------------------------------------------- _include / _revinclude

    def include_specs(self) -> List["IncludeSpec"]:
        """The ``_include`` / ``_revinclude`` parameters (with ``:iterate``, or
        ``:recurse`` in STU3), validated."""
        specs: List[IncludeSpec] = []
        for kind in ("_include", "_revinclude"):
            for value, iterate in self.result_params.get(kind, []):
                specs.extend(self.parse_include(kind, value, iterate))
        return specs

    def parse_include(self, kind: str, value: str, iterate: bool):
        """``*``, ``Source:*``, ``Source:param`` or ``Source:param:Target``."""
        if value == "*":
            return [IncludeSpec(kind, "*", "*", None, None, iterate)]
        parts = value.split(":")
        if len(parts) < 2 or len(parts) > 3 or not all(parts):
            raise ValidationError(
                f"bad {kind} param '{value}', "
                "should be Resource:search_param[:target_type]"
            )
        source_type, param_code = parts[0], parts[1]
        target_type = parts[2] if len(parts) == 3 else None
        source_context = SearchContext(self.context.engine, source_type)
        if param_code == "*":
            return [
                IncludeSpec(kind, source_type, sp.code, sp, target_type, iterate)
                for sp in self.reference_params(source_type)
                if target_type is None or target_type in reference_targets(sp)
            ]

        ref_param: SearchParameter = source_context._get_search_param_definitions(
            param_code
        )[0]
        if ref_param.type != "reference":
            raise ValidationError(
                f"search parameter {source_type}.{param_code} "
                f"must be of type 'reference', got {ref_param.type}"
            )
        if target_type and target_type not in (ref_param.target or []):
            if kind == "_include":
                raise ValidationError(
                    f"the search param {source_type}.{param_code} may refer"
                    f" to {', '.join(ref_param.target)}, not to {target_type}"
                )
            raise ValidationError(
                f"invalid reference {source_type}.{param_code} "
                f"({','.join(ref_param.target)}) in the current search context "
                f"({','.join(self.context.resource_types)})"
            )
        return [
            IncludeSpec(kind, source_type, param_code, ref_param, target_type, iterate)
        ]

    def reference_params(self, resource_type: str) -> List[SearchParameter]:
        """The reference search parameters of a resource type."""
        try:
            definition = SearchContext(self.context.engine, resource_type).definitions[
                0
            ]
        except Exception:  # unknown resource type
            return []
        params = []
        for code in definition:
            sp = getattr(definition, code)
            if sp.type == "reference" and sp.expression:
                params.append(sp)
        return params

    def all_resource_types(self) -> List[str]:
        storage = SEARCH_PARAMETERS_STORAGE.get(
            FHIR_VERSION.normalize(self.context.engine.fhir_release).name
        )
        return [t for t in storage if t not in ("Resource", "DomainResource")]

    def resolve_includes(
        self, main_result: EngineResult
    ) -> Generator[QueryResult, EngineResult, List[EngineResult]]:
        """Resources to include for the matches of this page. ``:iterate``
        specs are applied again to what was included, up to
        ``INCLUDE_MAX_ITERATIONS`` rounds. Entries are unique and a match is
        never included again."""
        specs = self.include_specs()
        seen = {row_key(row) for row in main_result.body}
        results: List[EngineResult] = []
        if self.result_params.get("_graph"):
            rows = yield from resolve_graph(self, list(main_result.body), seen)
            if rows:
                body = EngineResultBody()
                for row in rows:
                    body.append(row)
                results.append(EngineResult(EngineResultHeader(total=len(rows)), body))
        if not specs:
            return results
        frontier = list(main_result.body)
        rounds = 0
        while frontier and rounds <= INCLUDE_MAX_ITERATIONS:
            active = [spec for spec in specs if rounds == 0 or spec.iterate]
            if not active:
                break
            added: List = []
            for spec in active:
                for query in self.include_queries_for(spec, frontier, seen):
                    result = yield query
                    rows = [r for r in result.body if row_key(r) not in seen]
                    if not rows:
                        continue
                    seen.update(row_key(r) for r in rows)
                    body = EngineResultBody()
                    for row in rows:
                        body.append(row)
                    results.append(
                        EngineResult(EngineResultHeader(total=len(rows)), body)
                    )
                    added.extend(rows)
            frontier = added
            rounds += 1
        return results

    def include_queries_for(self, spec: "IncludeSpec", rows, seen) -> List[QueryResult]:
        """Queries fetching what ``spec`` includes for ``rows``."""
        if spec.kind == "_include":
            if spec.source_type == "*":
                specs = [
                    IncludeSpec(spec.kind, t, sp.code, sp, None, spec.iterate)
                    for t in sorted({row_key(r)[0] for r in rows})
                    for sp in self.reference_params(t)
                ]
            else:
                specs = [spec]
            references: Dict[str, Set[str]] = {}
            for sub_spec in specs:
                source_rows = [r for r in rows if row_key(r)[0] == sub_spec.source_type]
                if not source_rows:
                    continue
                body = EngineResultBody()
                for row in source_rows:
                    body.append(row)
                found = EngineResult(
                    EngineResultHeader(total=len(source_rows)), body
                ).extract_references(sub_spec.ref_param)
                allowed = (
                    [sub_spec.target_type]
                    if sub_spec.target_type
                    else list(sub_spec.ref_param.target or [])
                )
                for resource_type, ids in found.items():
                    if resource_type not in allowed and "Resource" not in allowed:
                        continue
                    references.setdefault(resource_type, set()).update(
                        i for i in ids if (resource_type, i) not in seen
                    )
            references = {t: ids for t, ids in references.items() if ids}
            if not references:
                return []
            terms: List = []
            for resource_type, ids in sorted(references.items()):
                try:
                    search_context = SearchContext(self.context.engine, resource_type)
                    normalized = search_context.normalize_param(
                        "_id", [",".join(sorted(ids))]
                    )
                except (KeyError, AttributeError, ValidationError):
                    continue  # not a resource type of this release
                self.add_term(normalized, terms)
            # one term per type: the dialect applies each to its own type
            types = sorted(references)
            builder = Q_(types, self.context.engine).where(*terms)
            return [builder(unrestricted=self.context.unrestricted)]

        # _revinclude: resources of the source type pointing at the rows
        if spec.source_type == "*":
            row_types = {row_key(r)[0] for r in rows}
            pairs = [
                (t, sp)
                for t in self.all_resource_types()
                for sp in self.reference_params(t)
                if row_types & set(reference_targets(sp) or [])
            ]
        else:
            pairs = [(spec.source_type, spec.ref_param)]
        queries: List[QueryResult] = []
        by_source: Dict[str, List] = {}
        for source_type, ref_param in pairs:
            targets = (
                [spec.target_type]
                if spec.target_type
                else list(reference_targets(ref_param) or ref_param.target or [])
            )
            refs = sorted(
                f"{t}/{i}"
                for t, i in {row_key(r) for r in rows}
                if t in targets or "Resource" in targets
            )
            if refs:
                by_source.setdefault(source_type, []).append((ref_param, refs))
        for source_type, items in sorted(by_source.items()):
            context = SearchContext(self.context.engine, source_type)
            terms: List = []
            for ref_param, refs in items:
                try:
                    normalized = context.normalize_param(ref_param.code, [",".join(refs)])
                    self.add_term(normalized, terms)
                except NotImplementedError:
                    continue
            if not terms:
                continue
            if len(terms) > 1:
                terms = [G_(*terms, path=None, type_=GroupType.DECOUPLED).match_any()]
            builder = Q_([source_type], self.context.engine).where(*terms)
            queries.append(builder(unrestricted=self.context.unrestricted))
        return queries

    def add_term(self, normalized_data, terms_container):
        """ """
        if isinstance(normalized_data, CompositeTuple):
            terms = []
            for component in normalized_data:
                self.add_term(component, terms)
            group = G_(
                *terms, path=normalized_data.base_path, type_=GroupType.COUPLED
            )
            terms_container.append(group)
            return group

        if isinstance(normalized_data, ComputedPresence):
            term = self.create_presence_term(normalized_data)
            terms_container.append(term)
            return term

        if isinstance(normalized_data, AnyOf):
            # paths of an unsupported type (e.g. Range or Timing next to Quantity
            # or dateTime), or whose type rejects the value (a boolean path for a
            # code), cannot match: they are left out as long as one path remains
            terms: List = []
            unsupported: List[Exception] = []
            for nd in normalized_data:
                try:
                    self.add_term(nd, terms)
                except (NotImplementedError, ValueError) as exc:
                    unsupported.append(exc)
            if not terms:
                raise unsupported[0]
            if len(terms) == 1:
                terms_container.append(terms[0])
                return terms[0]
            group_term = G_(
                *terms,
                path=self.entry_path(normalized_data[0]),
                type_=GroupType.DECOUPLED,
            )
            group_term.skip_invalid = True
            terms_container.append(group_term)
            return group_term

        if isinstance(normalized_data, list):
            if len(normalized_data) > 1:
                terms = list()
                for nd in normalized_data:
                    self.add_term(nd, terms)
                # I think we'll be there only in the case of composite search params
                # The Group path is only needed to build nested queries so using
                # whichever component path should be ok.
                # This could still use a refacto though...
                group_term = G_(*terms, path=nd[0], type_=GroupType.COUPLED)
                terms_container.append(group_term)
                return group_term

            else:
                normalized_data = normalized_data[0]

        path_, param_value, modifier = normalized_data

        if path_._where is not None:
            if path_._where.type == WhereConstraintType.T3:
                if path_._where.name == "url" and path_.path.endswith(".extension"):
                    term = self.create_extension_term(path_, param_value, modifier)
                    terms_container.append(term)
                    return term
                raise NotImplementedError(
                    f"Can't perform search on {path_._raw}: unsupported filter"
                )
        elif path_._is is not None:
            raise NotImplementedError

        param_type = getattr(path_, "search_param_type", None)
        negate = False
        if param_type == "token" and modifier in ("in", "not-in", "below", "above"):
            # terminology: the value stands for a set of codes
            param_value = self.expand_token_value(param_value, modifier)
            negate = modifier == "not-in"
            modifier = None

        if modifier in ("missing", "exists"):
            term = self.create_exists_term(path_, param_value, modifier)

        elif (
            hasattr(path_.context.get_real_type_class(), "is_primitive")
            and not path_.context.get_real_type_class().is_primitive()
        ):
            # we need normalization
            klass_name = path_.context.get_real_type_class().fhir_type_name()
            if klass_name == "Reference":
                if modifier == "identifier":
                    path_ = path_ / "identifier"
                    term_factory = self.create_identifier_term
                elif modifier in ("text", "text-advanced"):
                    path_ = path_ / "display"
                    term_factory = self.create_term
                else:
                    term_factory = self.create_reference_term
            elif klass_name == "Identifier":
                term_factory = self.create_identifier_term
            elif klass_name in QUANTITY_TYPES:
                term_factory = self.create_quantity_term
            elif klass_name == "CodeableConcept":
                term_factory = self.create_codeableconcept_term
            elif klass_name == "Coding":
                term_factory = self.create_coding_term
            elif klass_name == "Address":
                term_factory = self.create_address_term
            elif klass_name == "ContactPoint":
                term_factory = self.create_contactpoint_term
            elif klass_name == "HumanName":
                term_factory = self.create_humanname_term
            elif klass_name == "Money":
                term_factory = self.create_money_term
            elif klass_name == "Period":
                term_factory = self.create_period_term
            elif klass_name == "Range":
                term_factory = self.create_range_element_term
            elif klass_name == "Timing":
                term_factory = self.create_timing_term
            elif klass_name == "Attachment":
                term_factory = self.create_attachment_term
            elif klass_name == "Narrative":
                term_factory = self.create_narrative_term
            elif klass_name == "SampledData":
                # a series of measurements, not a value a quantity can match
                raise NotImplementedError(
                    "SampledData values are not searchable by quantity"
                )
            else:
                raise NotImplementedError(
                    f"Can't perform search on element of type {klass_name}"
                )
            term = term_factory(path_, param_value, modifier)
        else:
            term = self.create_term(path_, param_value, modifier)
        if negate:
            # ``:not-in``: no value of the element is in the value set
            terms = term if isinstance(term, list) else [term]
            term = G_(*terms, path=path_, type_=GroupType.DECOUPLED).match_no_one()
        if isinstance(term, list):
            terms_container.extend(term)
        else:
            terms_container.append(term)

    @staticmethod
    def entry_path(entry):
        """Element path of a normalized entry (``None``: the resource)."""
        if isinstance(entry, CompositeTuple):
            return entry.base_path
        if isinstance(entry, ComputedPresence):
            return entry.paths[0]
        if isinstance(entry, AnyOf):
            return Search.entry_path(entry[0])
        return entry[0]

    def expand_token_value(self, param_value, modifier):
        """Replace each value of a token test by the codes it stands for:
        the members of a value set (``:in`` / ``:not-in``) or the code with its
        descendants (``:below``) or ancestors (``:above``)."""
        terminology = get_terminology(self.context.engine)

        def expand(leaf):
            operator_, value = leaf
            if modifier in ("in", "not-in"):
                codes = terminology.expand(unescape_value(value))
            else:
                parts = split_escaped(value, "|")
                if len(parts) == 1:
                    system, code = None, unescape_value(parts[0])
                elif len(parts) == 2 and parts[1]:
                    system, code = unescape_value(parts[0]) or None, unescape_value(
                        parts[1]
                    )
                else:
                    raise ValidationError(
                        f"``:{modifier}`` expects ``[system|]code``, got ``{value}``."
                    )
                codes = terminology.subsumption(system, code, modifier)
            values = [
                (
                    "eq",
                    f"{escape_value(system)}|{escape_value(code)}"
                    if system
                    else escape_value(code),
                )
                for system, code in codes
            ]
            if len(values) == 1:
                return values[0]
            return (None, values)

        return map_normalized_values(param_value, expand)

    def create_presence_term(self, presence: "ComputedPresence"):
        """Computed boolean ``X.exists() and X != false`` (Patient
        ``deceased``): true when the boolean choice is true or another choice
        (e.g. a date) is present."""
        _, value = presence.value
        if value not in ("true", "false"):
            raise ValidationError(
                f"``{presence.code}`` expects ``true`` or ``false``, got ``{value}``."
            )
        terms: List = []
        for path in presence.paths:
            if path.context.type_name == "boolean":
                terms.append(T_(path) == V_("true"))
            else:
                terms.append(self.value_exists_term(path))
        group = G_(*terms, path=presence.paths[0], type_=GroupType.DECOUPLED)
        wanted = value == "true"
        if presence.modifier == "not":
            wanted = not wanted
        elif presence.modifier in ("missing", "exists"):
            wanted = (value == "true") == (presence.modifier == "exists")
        return group.match_any() if wanted else group.match_no_one()

    def create_extension_term(self, path_, param_value, modifier):
        """Search on an extension value: ``Patient.extension('url').value``
        (``extension.where(url='...')``) - the url and the value must match in the
        same extension."""
        url = path_._where.value
        subpath = path_._where.subpath or "value"
        extension_path = ElementPath.from_el_path(path_.path)
        extension_path.finalize(self.context.engine)
        extension_path.search_param_type = path_.search_param_type
        url_term = exact_(T_(extension_path / "url") == V_(url))
        if modifier in ("missing", "exists"):
            present = (param_value[1] == "true") == (modifier == "exists")
            group = G_(url_term, path=extension_path, type_=GroupType.COUPLED)
            return group if present else group.match_no_one()

        value_names = (
            [subpath]
            if subpath != "value"
            else EXTENSION_VALUE_TYPES.get(path_.search_param_type, [])
        )
        value_terms = []
        for name in value_names:
            try:
                value_path = extension_path / name
            except Exception:  # not a value type of this release
                continue
            value_terms.append((value_path, param_value, modifier))
        if not value_terms:
            raise NotImplementedError(
                f"no extension value type for ``{path_.search_param_type}`` searches"
            )
        terms: List = []
        self.add_term(AnyOf(value_terms), terms)
        return G_(url_term, *terms, path=extension_path, type_=GroupType.COUPLED)

    def create_identifier_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = [
                self.create_identifier_term(path_, value, modifier)
                for value in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_identifier_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_identifier_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        if isinstance(original_value, list):
            terms = [
                self.single_valued_identifier_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group

        has_pipe = has_unescaped(original_value, "|")
        terms = list()

        if modifier == "of-type":
            # [system]|[code]|[value]: a type coding and the value, all required
            parts = split_escaped(original_value, "|")
            if len(parts) != 3 or not all(parts):
                raise ValidationError(
                    "``:of-type`` expects ``[system]|[code]|[value]``, "
                    f"got ``{original_value}``."
                )
            coding = path_ / "type" / "coding"
            terms.append(
                G_(
                    self.create_term(coding / "system", ("eq", parts[0]), None),
                    self.create_term(coding / "code", ("eq", parts[1]), None),
                    path=coding,
                    type_=GroupType.COUPLED,
                )
            )
            terms.append(self.create_term(path_ / "value", ("eq", parts[2]), None))

        elif modifier == "text" and not has_pipe:
            # xxx: should be validation error if value contained pipe
            # make identifier.type.text query
            path_1 = path_ / "type" / "text"
            term = self.create_term(path_1, value, modifier)

            terms.append(term)

        elif has_pipe:
            if original_value.startswith("|"):
                # ``|value``: the value, without a system
                path_1 = path_ / "value"
                new_value = (operator_, original_value[1:])

                term = self.create_term(path_1, new_value, modifier)
                terms.append(term)
                terms.append(not_exists_(path_ / "system"))

            elif split_escaped(original_value, "|")[-1] == "":
                path_1 = path_ / "system"
                new_value = (value[0], original_value[:-1])

                term = self.create_term(path_1, new_value, modifier)
                terms.append(term)

            else:
                parts = split_escaped(original_value, "|")
                try:
                    path_1 = path_ / "system"
                    new_value = (operator_, parts[0])
                    term = self.create_term(path_1, new_value, modifier)
                    terms.append(term)

                    path_2 = path_ / "value"
                    new_value = (operator_, parts[1])
                    term = self.create_term(path_2, new_value, modifier)
                    terms.append(term)

                except IndexError:
                    pass

        else:
            path_1 = path_ / "value"
            term = self.create_term(path_1, value, modifier)
            terms.append(term)

        return G_(*terms, path=path_, type_=GroupType.COUPLED)

    def create_quantity_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = [
                self.create_quantity_term(path_, value, modifier)
                for value in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_quantity_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_quantity_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_quantity_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group

        operator_eq = "eq"
        has_pipe = has_unescaped(original_value, "|")
        # modifier = text, no impact
        if has_pipe:
            terms = list()
            parts = split_escaped(original_value, "|")

            if len(parts) == 3:
                if parts[0]:
                    path_1 = path_ / "value"
                    new_value = (operator_, parts[0])
                    term = self.create_term(path_1, new_value, modifier)
                    terms.append(term)

                if parts[1]:
                    # check if val||unit or code
                    path_2 = path_ / "system"
                    new_value = (operator_eq, parts[1])
                    term = self.create_term(path_2, new_value, modifier)
                    terms.append(term)

                    path_3 = path_ / "code"
                    new_value = (operator_eq, parts[2])
                    term = self.create_term(path_3, new_value, modifier)
                    terms.append(term)
                else:
                    path_2 = path_ / "unit"
                    new_value = (operator_eq, parts[2])
                    term = self.create_term(path_2, new_value, modifier)
                    terms.append(term)

            elif len(parts) == 2:
                if parts[0]:
                    path_1 = path_ / "value"
                    new_value = (operator_, parts[0])
                    term = self.create_term(path_1, new_value, modifier)
                    terms.append(term)

                if parts[1]:
                    path_2 = path_ / "unit"
                    new_value = (operator_eq, parts[1])
                    term = self.create_term(path_2, new_value, modifier)
                    terms.append(term)
            else:
                # may be validation error
                raise NotImplementedError

            if len(terms) > 1:
                return G_(*terms, path=path_, type_=GroupType.COUPLED)
            else:
                return terms[0]
        else:
            path_1 = path_ / "value"
            return self.create_term(path_1, value, modifier)

    def create_coding_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = [
                self.create_coding_term(path_, value, modifier) for value in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_coding_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_coding_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_coding_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group

        has_pipe = has_unescaped(original_value, "|")
        terms = list()
        subpredicate_modifier = None if modifier == "not" else modifier

        if modifier in ("text", "text-advanced") and not has_pipe:
            path_1 = path_ / "display"

            term = self.create_term(path_1, value, modifier)
            terms.append(term)

        elif has_pipe:
            if original_value.startswith("|"):
                # ``|code``: the code, without a system
                path_1 = path_ / "code"
                new_value = (value[0], original_value[1:])

                term = self.create_term(path_1, new_value, subpredicate_modifier)
                terms.append(term)
                terms.append(not_exists_(path_ / "system"))

            elif split_escaped(original_value, "|")[-1] == "":
                path_1 = path_ / "system"
                new_value = (value[0], original_value[:-1])

                terms.append(self.create_term(path_1, new_value, subpredicate_modifier))

            else:
                parts = split_escaped(original_value, "|")
                terms = list()
                try:
                    path_1 = path_ / "system"
                    new_value = (value[0], parts[0])
                    term = self.create_term(path_1, new_value, subpredicate_modifier)
                    terms.append(term)

                    path_2 = path_ / "code"
                    new_value = (value[0], parts[1])
                    term = self.create_term(path_2, new_value, subpredicate_modifier)
                    terms.append(term)

                except IndexError:
                    pass
        else:
            path_1 = path_ / "code"
            terms.append(self.create_term(path_1, value, subpredicate_modifier))

        group = G_(*terms, path=path_, type_=GroupType.COUPLED)
        if modifier == "not":
            group.match_operator = MatchType.NONE
        return group

    def create_codeableconcept_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = [
                self.create_codeableconcept_term(path_, value, modifier)
                for value in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_codeableconcept_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_codeableconcept_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms_ = list()
            for val in original_value:
                term_ = self.single_valued_codeableconcept_term(path_, val, modifier)
                if IGroupTerm.providedBy(term_):
                    if term_.match_operator == MatchType.NONE:
                        # important!
                        term_.match_operator = None
                terms_.append(term_)
            # IN Like Group
            group = G_(*terms_, path=path_, type_=GroupType.DECOUPLED)
            if modifier == "not":
                group.match_operator = MatchType.NONE
            return group

        has_pipe = has_unescaped(original_value, "|")

        if modifier in ("text", "text-advanced") and not has_pipe:
            # the text of the concept or the display of any of its codings
            terms = [
                self.create_term(path_ / "text", value, modifier),
                self.single_valued_coding_term(path_ / "coding", value, modifier),
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED).match_any()

        else:
            path_1 = path_ / "coding"
            return self.single_valued_coding_term(path_1, value, modifier)

    def create_address_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = [
                self.create_address_term(path_, val, modifier) for val in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_address_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_address_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        if isinstance(original_value, list):
            terms = [
                self.single_valued_address_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group

        sub_modifier = None if modifier == "not" else modifier
        terms = [
            self.create_term(path_ / name, value, sub_modifier)
            for name in ADDRESS_STRING_ELEMENTS
            if self.has_element(path_, name)
        ]
        group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
        if modifier == "not":
            group.match_operator = MatchType.NONE
        else:
            group.match_operator = MatchType.ANY

        return group

    @staticmethod
    def has_element(path_, name) -> bool:
        """Whether the type of ``path_`` has an element ``name`` in this
        release."""
        model_class = getattr(path_.context.type_class, "model_class", None)
        if model_class is None:
            return True
        return any(f.alias == name for f in model_class.model_fields.values())

    def create_contactpoint_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = [
                self.create_contactpoint_term(path_, val, modifier)
                for val in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_contactpoint_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_contactpoint_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_contactpoint_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group

        if path_._where:
            if path_._where.type != WhereConstraintType.T1:
                raise NotImplementedError

            assert path_._where.name == "system"

            terms = [
                self.create_term(
                    path_ / "system", (value[0], path_._where.value), None
                ),
                self.create_term(path_ / "value", value, None),
            ]
            group = G_(*terms, path=path_, type_=GroupType.COUPLED)  # Term or Group
        else:
            # a ContactPoint token matches its value
            terms = [self.create_term(path_ / "value", value, None)]
            group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group
        if modifier == "not":
            group.match_operator = MatchType.NONE
        else:
            group.match_operator = MatchType.ANY

        return group

    def create_humanname_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = [
                self.create_humanname_term(path_, val, modifier) for val in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_humanname_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_humanname_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_humanname_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group

        sub_modifier = None if modifier == "not" else modifier
        terms = [
            self.create_term(path_ / name, value, sub_modifier)
            for name in HUMANNAME_STRING_ELEMENTS
        ]
        group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
        if modifier == "not":
            group.match_operator = MatchType.NONE
        else:
            group.match_operator = MatchType.ANY

        return group

    def create_reference_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = [
                self.create_reference_term(path_, value, modifier)
                for value in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_reference_term(path_, param_value, modifier)

    def single_valued_reference_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_reference_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)

        if path_._where:
            if path_._where.type != WhereConstraintType.T2:
                raise NotImplementedError
            # ``where(resolve() is X)``: plain ids were already narrowed to ``X/id``
            # (``SearchContext.path_param_value``)

        new_path = path_ / "reference"
        variants = reference_variants(
            unescape_value(original_value), self.server_base()
        )
        if len(variants) == 1 and variants[0][0] == "eq":
            return self.create_term(new_path, value, modifier)
        sub_modifier = None if modifier == "not" else modifier
        terms = [
            (
                self.create_term(new_path, ("eq", escape_value(v)), sub_modifier)
                if op == "eq"
                else sa_(T_(new_path), V_(v))
            )
            for op, v in variants
        ]
        group = G_(*terms, path=new_path, type_=GroupType.DECOUPLED)
        return group.match_no_one() if modifier == "not" else group.match_any()

    def server_base(self) -> Optional[str]:
        """Base url of the server (``http://example.org/fhir``), when the engine
        knows the current url."""
        try:
            url = self.context.engine.current_url()
        except Exception:  # the engine does not know the request
            return None
        if url is None:
            return None
        from fhirpath.search.utils import BundleWrapper

        return str(BundleWrapper.calculate_fhir_base_url(url)).rstrip("/")

    def create_exists_term(self, path_, param_value, modifier):
        """``:missing`` (and the non-standard ``:exists``). An element that only
        carries extensions (e.g. a data-absent-reason) counts as missing."""
        if isinstance(param_value, tuple):
            operator_, original_value = param_value
            if (original_value == "true" and modifier == "exists") or (
                original_value == "false" and modifier == "missing"
            ):
                return self.value_exists_term(path_)
            elif (original_value == "true" and modifier == "missing") or (
                original_value == "false" and modifier == "exists"
            ):
                term = self.value_exists_term(path_)
                if IGroupTerm.providedBy(term):
                    return term.match_no_one()
                return not_(term)

            raise NotImplementedError

        raise NotImplementedError

    # elements that do not make a value present
    NON_VALUE_ELEMENTS = ("id", "extension", "modifierExtension", "fhir_comments")

    def value_exists_term(self, path_):
        """The element has a value: a primitive value, or any element of a
        complex type other than ``id`` and extensions."""
        model_class = getattr(path_.context.type_class, "model_class", None)
        if path_.context.type_is_primitive or model_class is None:
            return exists_(path_)
        terms = []
        for field in model_class.model_fields.values():
            extra = field.json_schema_extra or {}
            if not extra.get("element_property") or (
                field.alias in self.NON_VALUE_ELEMENTS
            ):
                continue
            try:
                terms.append(exists_(path_ / field.alias))
            except Exception:  # an element the path layer does not know
                continue
        if not terms:
            return exists_(path_)
        group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
        return group.match_any()

    def create_money_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = [
                self.create_money_term(path_, value, modifier) for value in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_money_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_money_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_money_term(path_, value, modifier)
                for value in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)

        if self.context.engine.fhir_release == FHIR_VERSION.STU3:
            # make legacy
            return self._single_valued_money_term_stu3(path_, value, modifier)

        operator_eq = "eq"
        has_pipe = has_unescaped(original_value, "|")
        # modifier = text, no impact
        if has_pipe:
            terms = list()
            parts = split_escaped(original_value, "|")
            if len(parts) == 3:
                # quantity syntax [number]|[system]|[code]: the code is the currency
                # (system urn:iso:std:iso:4217, the only one Money.currency uses)
                parts = [parts[0], parts[2]]
                original_value = "|".join(parts)

            if original_value.startswith("|"):
                new_value = (operator_eq, original_value[1:])
                path_1 = path_ / "currency"
                term = self.create_term(path_1, new_value, modifier)
                terms.append(term)

            elif len(parts) == 2:
                path_1 = path_ / "value"
                new_value = (operator_, parts[0])
                term = self.create_term(path_1, new_value, modifier)
                terms.append(term)

                if parts[1]:
                    # check if val||unit or code
                    path_2 = path_ / "currency"
                    new_value = (operator_eq, parts[1])
                    term = self.create_term(path_2, new_value, modifier)
                    terms.append(term)

            else:
                # may be validation error
                raise NotImplementedError

            if len(terms) > 1:
                return G_(*terms, path=path_, type_=GroupType.COUPLED)
            else:
                return terms[0]
        else:
            path_1 = path_ / "value"
            return self.create_term(path_1, value, modifier)

    def _single_valued_money_term_stu3(self, path_, value, modifier):
        """ """
        assert self.context.engine.fhir_release == FHIR_VERSION.STU3
        return self.single_valued_quantity_term(path_, value, modifier)

    def _each_value(self, path_, param_value, modifier, single):
        """Apply ``single`` to every value: AND list -> list of terms, OR tuple
        -> DECOUPLED group."""
        if isinstance(param_value, list):
            return [self._each_value(path_, v, modifier, single) for v in param_value]
        operator_, original_value = param_value
        if isinstance(original_value, list):
            terms = [
                self._each_value(path_, v, modifier, single) for v in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED).match_any()
        return single(path_, param_value, modifier)

    def create_range_element_term(self, path_, param_value, modifier):
        """Quantity or number search on a ``Range``: the resource value is the
        explicit range ``[low, high]`` (a missing bound is open)."""
        return self._each_value(
            path_, param_value, modifier, self.single_valued_range_element_term
        )

    def single_valued_range_element_term(self, path_, value, modifier):
        operator_, original_value = value
        parts = split_escaped(original_value, "|")
        number = unescape_value(parts[0])
        low, high = path_ / "low", path_ / "high"
        low_value, high_value = low / "value", high / "value"

        def cmp(path, op, bound):
            return self.create_term(path, (op, bound), None)

        if operator_ in ("eq", "ne", "ap"):
            p_low, p_high, high_inclusive = number_bounds(number, operator_, "decimal")
            inside = G_(
                cmp(low_value, "ge", p_low),
                cmp(high_value, "le" if high_inclusive else "lt", p_high),
                path=path_,
                type_=GroupType.COUPLED,
            )
            if operator_ == "ap":
                # overlap
                inside = G_(
                    cmp(low_value, "le", p_high),
                    cmp(high_value, "ge", p_low),
                    path=path_,
                    type_=GroupType.COUPLED,
                )
            terms = [inside]
            if operator_ == "ne":
                terms = [inside.match_no_one()]
        elif operator_ in ("gt", "ge"):
            terms = [
                G_(
                    cmp(high_value, operator_, number),
                    G_(
                        exists_(low_value),
                        not_exists_(high_value),
                        path=path_,
                        type_=GroupType.COUPLED,
                    ),
                    path=path_,
                    type_=GroupType.DECOUPLED,
                ).match_any()
            ]
        elif operator_ in ("lt", "le"):
            terms = [
                G_(
                    cmp(low_value, operator_, number),
                    G_(
                        exists_(high_value),
                        not_exists_(low_value),
                        path=path_,
                        type_=GroupType.COUPLED,
                    ),
                    path=path_,
                    type_=GroupType.DECOUPLED,
                ).match_any()
            ]
        elif operator_ == "sa":
            terms = [cmp(low_value, "gt", number)]
        elif operator_ == "eb":
            terms = [cmp(high_value, "lt", number)]
        else:
            raise NotImplementedError(f"prefix {operator_} not handled for ranges.")

        # units: [number]|[system]|[code] or [number]||[code]
        if len(parts) == 3 and parts[2]:
            for bound in (low, high):
                if parts[1]:
                    unit_terms = [
                        self.create_term(bound / "system", ("eq", parts[1]), None),
                        self.create_term(bound / "code", ("eq", parts[2]), None),
                    ]
                    unit = G_(*unit_terms, path=bound, type_=GroupType.COUPLED)
                else:
                    unit = G_(
                        self.create_term(bound / "code", ("eq", parts[2]), None),
                        self.create_term(bound / "unit", ("eq", parts[2]), None),
                        path=bound,
                        type_=GroupType.DECOUPLED,
                    ).match_any()
                terms.append(
                    G_(
                        unit,
                        not_exists_(bound / "value"),
                        path=bound,
                        type_=GroupType.DECOUPLED,
                    ).match_any()
                )
        return G_(*terms, path=path_, type_=GroupType.COUPLED)

    def create_timing_term(self, path_, param_value, modifier):
        """Date search on a ``Timing``: its events or the bounds of its
        repetition."""
        def single(path, value, modifier_):
            terms = [self.create_term(path / "event", value, modifier_)]
            try:
                bounds = path / "repeat" / "boundsPeriod"
            except Exception:  # no boundsPeriod in this release
                bounds = None
            if bounds is not None:
                terms.append(self.single_valued_period_term(bounds, value, modifier_))
            return G_(*terms, path=path, type_=GroupType.DECOUPLED).match_any()

        return self._each_value(path_, param_value, modifier, single)

    # element of an Attachment searched by each parameter type
    ATTACHMENT_ELEMENTS = {
        "uri": ("url",),
        "string": ("title",),
        "token": ("contentType", "language"),
        "date": ("creation",),
    }

    def create_attachment_term(self, path_, param_value, modifier):
        names = self.ATTACHMENT_ELEMENTS.get(getattr(path_, "search_param_type", None))
        if not names:
            raise NotImplementedError(
                f"Can't perform a {path_.search_param_type} search on an Attachment"
            )
        terms = [self.create_term(path_ / name, param_value, modifier) for name in names]
        if len(terms) == 1:
            return terms[0]
        return G_(*terms, path=path_, type_=GroupType.DECOUPLED).match_any()

    def create_narrative_term(self, path_, param_value, modifier):
        """Full-text search on the narrative (``_text``)."""
        return self.create_term(path_ / "div", param_value, "text")

    def create_period_term(self, path_, param_value, modifier):
        if isinstance(param_value, list):
            terms = [
                self.single_valued_period_term(path_, value, modifier)
                for value in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_period_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_period_term(self, path_, value, modifier):
        operator, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_period_term(path_, val, modifier)
                for val in original_value
            ]
            # IN Like Group
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)

        if operator == "eq":
            terms = [
                self.create_term(path_ / "start", ("ge", original_value), modifier),
                self.create_term(path_ / "end", ("le", original_value), modifier),
            ]
            type_ = GroupType.COUPLED
        elif operator == "ne":
            terms = [
                self.create_term(path_ / "start", ("lt", original_value), modifier),
                self.create_term(path_ / "end", ("gt", original_value), modifier),
                not_exists_(path_ / "start"),
                not_exists_(path_ / "end"),
            ]
            type_ = GroupType.DECOUPLED
        elif operator == "gt":
            terms = [
                self.create_term(path_ / "end", ("gt", original_value), modifier),
                not_exists_(path_ / "end"),
            ]
            type_ = GroupType.DECOUPLED
        elif operator == "lt":
            terms = [
                self.create_term(path_ / "start", ("lt", original_value), modifier),
            ]
            type_ = GroupType.COUPLED
        elif operator == "ge":
            terms = [
                self.create_term(path_ / "end", ("ge", original_value), modifier),
                not_exists_(path_ / "end"),
            ]
            type_ = GroupType.DECOUPLED
        elif operator == "le":
            terms = [
                self.create_term(path_ / "start", ("le", original_value), modifier),
            ]
            type_ = GroupType.COUPLED
        elif operator == "sa":
            terms = [
                self.create_term(path_ / "start", ("gt", original_value), modifier),
            ]
            type_ = GroupType.COUPLED
        elif operator == "eb":
            terms = [
                self.create_term(path_ / "end", ("lt", original_value), modifier),
            ]
            type_ = GroupType.COUPLED
        elif operator == "ap":
            # the period overlaps the value's range widened by 10 % of the gap
            # between now and the date
            low, high, _ = approximate_date_range(unescape_value(original_value))
            low, high = low.isoformat(), high.isoformat()
            start_terms = [self.create_term(path_ / "start", ("le", high), modifier)]
            start_group = G_(*start_terms, path=path_, type_=GroupType.COUPLED)
            end_terms = [
                self.create_term(path_ / "end", ("ge", low), modifier),
                not_exists_(path_ / "end"),
            ]
            end_group = G_(*end_terms, path=path_, type_=GroupType.DECOUPLED)
            terms = [start_group, end_group]
            type_ = GroupType.COUPLED
        else:
            raise NotImplementedError(f"prefix {operator} not handled for periods.")

        return G_(*terms, path=path_, type_=type_)

    def validate_pre_term(self, operator_, path_, value, modifier):
        """ """
        if modifier in ("above", "below") and operator_ in ("sa", "eb"):
            raise ValidationError(
                "You cannot use modifier (above,below) and prefix (sa,eb) at a time"
            )
        if modifier == "contains" and operator_ != "eq":
            raise NotImplementedError(
                "In case of :contains modifier, only eq prefix is supported"
            )

    def create_term(self, path_, value, modifier):
        """Term on a primitive element. The match semantics follow the search
        parameter type (``path_.search_param_type``):

        * string: case-insensitive starts-with (``:exact`` exact, ``:contains``
          anywhere, ``:text`` all words);
        * token: exact, case-sensitive match of the code (case-insensitive on
          string elements); ``:text`` / ``:code-text`` starts-with,
          ``:text-advanced`` all words;
        * uri: exact (``:below`` / ``:above`` by path segments);
        * number / date / quantity: the implicit range of the value
          (``100`` -> [99.5, 100.5), ``2013-01`` -> the whole month).
        """
        assert path_.context.get_real_type_class() is bool or (
            getattr(path_.context.get_real_type_class(), "is_primitive", None)
            and path_.context.get_real_type_class().is_primitive() is True
        )

        if isinstance(value, tuple):
            operator_, original_value = value
            # do validate first
            self.validate_pre_term(operator_, path_, value, modifier)
            if isinstance(original_value, list):
                # we force IN will have equal or not equal operator_
                # xxx: should be validated already
                terms_ = list()
                for val in original_value:
                    subpredicate_modifier = None if modifier == "not" else modifier
                    term_ = self.create_term(path_, val, subpredicate_modifier)
                    terms_.append(term_)
                # IN Like Group
                group = G_(*terms_, path=path_, type_=GroupType.DECOUPLED)
                if modifier == "not":
                    return group.match_no_one()
                else:
                    return group.match_any()

            element_type = path_.context.type_name
            param_type = getattr(path_, "search_param_type", None)
            if param_type == "token" and has_unescaped(original_value, "|"):
                # a code element has an implicit system: ``[system]|[code]``
                # and ``|[code]`` test the code, ``[system]|`` any code
                parts = split_escaped(original_value, "|")
                if len(parts) != 2:
                    raise ValidationError(
                        f"Invalid token ``{original_value}`` for {path_._raw}."
                    )
                if not parts[1]:
                    return exists_(path_)
                original_value = parts[1]
            raw_value = unescape_value(original_value)

            if isinstance(raw_value, str) and param_type not in ("string", "token"):
                if element_type in NUMBER_TYPES and operator_ in ("eq", "ne", "ap"):
                    bounds = number_bounds(raw_value, operator_, element_type)
                    return self.create_range_term(path_, operator_, bounds, modifier)
                if element_type in DATE_TYPES:
                    if operator_ in ("eq", "ne", "ap"):
                        bounds = date_bounds(raw_value, operator_, element_type)
                        return self.create_range_term(
                            path_, operator_, bounds, modifier
                        )
                    if operator_ in DATE_PREFIX_BOUNDS:
                        which, operator_ = DATE_PREFIX_BOUNDS[operator_]
                        raw_value = date_bound(raw_value, element_type, which)

            if param_type == "uri" and modifier in ("below", "above"):
                return self.create_uri_hierarchy_term(path_, raw_value, modifier)

            term = T_(path_)
            if modifier == "not":
                term = not_(term)
            elif modifier == "below" and operator_ == "eq":
                operator_ = "sa"
            elif modifier == "above" and operator_ == "eq":
                operator_ = "eb"
            elif modifier == "exact":
                term = exact_(term)
            val = V_(raw_value)

            if operator_ == "eq":
                if modifier == "contains":
                    term = contains_(term, val)
                else:
                    term = term == val
                    self.set_match_type(term, param_type, element_type, modifier)
            elif operator_ == "ne":
                term = term != val
            elif operator_ == "lt":
                term = term < val
            elif operator_ == "le":
                term = term <= val
            elif operator_ == "gt":
                term = term > val
            elif operator_ == "ge":
                term = term >= val
            elif operator_ == "sa":
                term = sa_(term, val)
            elif operator_ == "eb":
                term = eb_(term, val)
            else:
                raise NotImplementedError

            return term

        elif isinstance(value, list):
            # Group Term
            terms = list()
            for val in value:
                term = self.create_term(path_, val, modifier)
                terms.append(term)

            g_term = G_(*terms, path=path_, type_=GroupType.COUPLED)
            return g_term

    @staticmethod
    def set_match_type(term, param_type, element_type, modifier):
        """Match semantics of an equality test (see ``create_term``)."""
        if modifier in ("text", "code-text") or (
            param_type == "string" and modifier is None
        ):
            term.set_match_type(TermMatchType.STARTWITH)
        elif modifier == "text-advanced" or (
            param_type == "string" and modifier == "text"
        ):
            term.set_match_type(TermMatchType.FULLTEXT)
        elif param_type in ("token", "uri") and modifier in (None, "not"):
            term.set_match_type(TermMatchType.EXACT)
            # a token on a string element is a case-insensitive full match
            term.case_insensitive = param_type == "token" and element_type in (
                "string",
                "markdown",
            )

    def create_range_term(self, path_, operator_, bounds, modifier):
        """``eq`` / ``ap``: the element lies in the range; ``ne``: outside it
        (prefixes never match a missing element)."""
        low, high, high_inclusive = bounds
        if operator_ == "ne":
            below = T_(path_) < V_(low)
            above = (T_(path_) > V_(high)) if high_inclusive else T_(path_) >= V_(high)
            group = G_(below, above, path=path_, type_=GroupType.DECOUPLED)
            return group.match_any()
        term = T_(path_) == V_(low)
        term.bounds = bounds
        if modifier == "not":
            term = not_(term)
        return term

    def create_uri_hierarchy_term(self, path_, value, modifier):
        """``url:below=http://acme.org/fhir`` matches the url and every url
        below it (by path segment); ``:above`` the url and its ancestors.
        ``url|version`` (canonical) compares versions instead."""
        if "|" in value:
            url, _, version = value.partition("|")
            if modifier == "below":
                terms = [
                    exact_(T_(path_) == V_(value)),
                    sa_(T_(path_), V_(f"{url}|{version}.")),
                ]
            else:
                parts = version.split(".")
                values = [url] + [
                    f"{url}|{'.'.join(parts[:i])}" for i in range(1, len(parts) + 1)
                ]
                terms = [exact_(T_(path_) == V_(v)) for v in values]
        elif modifier == "below":
            base = value.rstrip("/")
            terms = [
                exact_(T_(path_) == V_(base)),
                sa_(T_(path_), V_(base + "/")),
            ]
            if base != value:
                terms.append(exact_(T_(path_) == V_(value)))
        else:
            if not uri_scheme.match(value):
                # URNs and OIDs have no hierarchy
                return exact_(T_(path_) == V_(value))
            scheme, _, rest = value.partition("://")
            segments = rest.rstrip("/").split("/")
            values = [
                f"{scheme}://{'/'.join(segments[:i])}"
                for i in range(1, len(segments) + 1)
            ]
            values += [v + "/" for v in values]
            terms = [exact_(T_(path_) == V_(v)) for v in values]
        group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
        return group.match_any()

    def validate(self):
        """ """
        errors = set()

        for search_param in self.search_params:

            param_name = search_param.split(":")[0]
            try:
                self.context._get_search_param_definitions(param_name)
            except ValidationError as e:
                errors.add(str(e))

        if len(errors) > 0:
            raise ValidationError(", ".join([e for e in errors]))
        # xxx: later more

    @staticmethod
    def validate_normalized_value(param_name, param_value, modifier):
        """
        :param param_name:
        :param param_value:
        :param modifier:
        """
        if modifier in ("missing", "exists"):
            if not isinstance(param_value, tuple):
                raise ValidationError(
                    "Multiple values are not allowed for missing(exists) search"
                )

            if not param_value[1] in ("true", "false"):

                raise ValidationError(
                    "Only ´true´ or ´false´ as value is "
                    "allowed for missing(exists) search"
                )

    def attach_where_terms(self, builder):
        terms_container = list()
        # we make sure that there are no duplicate keys!
        for param_name in set(self.search_params):
            raw_value = list(self.search_params.getall(param_name, []))
            if param_name in self.hierarchy_references:
                # resolved hierarchy: any of its references
                normalized_params = self.context.normalize_param(
                    param_name.split(":")[0],
                    [",".join(self.hierarchy_references[param_name])],
                )
                for np in normalized_params:
                    self.add_term(np, terms_container)
                continue
            if param_name in self.hierarchy_params():
                raise ValidationError(
                    f"``{param_name}`` is a hierarchy search: it is resolved when "
                    "the search is run."
                )
            normalized_params = self.context.normalize_param(param_name, raw_value)
            for np in normalized_params:
                self.add_term(np, terms_container)

        return builder.where(*terms_container)

    def sort_fields(self) -> List[Tuple[str, Optional[str], SortOrderType]]:
        """``_sort`` as ``(parameter, modifier, order)``: ``-date`` is
        descending, ``code:text`` sorts on the text of the code."""
        fields = []
        for sort_field in self.result_params.get("_sort", "").split(","):
            sort_field = sort_field.strip()
            if not sort_field:
                continue
            order = SortOrderType.ASC
            if sort_field.startswith("-"):
                order = SortOrderType.DESC
                sort_field = sort_field[1:]
            if "." in sort_field:
                # chained: ``subject:Patient.name`` (``:Patient`` is a type)
                fields.append((sort_field, None, order))
                continue
            name, _, modifier = sort_field.partition(":")
            if modifier and modifier != "text":
                raise ValidationError(
                    f"``_sort={sort_field}``: only the ``:text`` modifier is "
                    "supported for sorting."
                )
            fields.append((name, modifier or None, order))
        return fields

    def sort_leaves(self, path_, modifier) -> List[ElementPath]:
        """Primitive elements a parameter's element is sorted on: a HumanName
        by family then given name, a CodeableConcept by its code (``:text``:
        by its text), a Period by its start..."""
        type_class = path_.context.get_real_type_class()
        if getattr(type_class, "is_primitive", None) is None or type_class.is_primitive():
            return [path_]
        type_name = type_class.fhir_type_name()
        table = SORT_TEXT_LEAVES if modifier == "text" else SORT_LEAVES
        leaves = table.get(type_name) or SORT_LEAVES.get(type_name)
        if leaves is None:
            raise ValidationError(f"Cannot sort on an element of type {type_name}.")
        result = []
        for leaf in leaves:
            leaf_path = path_
            try:
                for name in leaf.split("."):
                    leaf_path = leaf_path / name
            except Exception:  # not an element of this release
                continue
            result.append(leaf_path)
        return result

    def attach_sort_terms(self, builder):
        """``_sort``: every path of each parameter, in priority order."""
        terms = list()
        for name, modifier, order in self.sort_fields():
            if "." in name:
                # chained sort: done in memory (``sorted_page``)
                continue
            for sort_param_def in self.context._get_search_param_definitions(name):
                if sort_param_def.type == "composite":
                    raise ValidationError(f"Cannot sort by composite parameter {name}.")
                for path_ in self.context.resolve_path_contexts(sort_param_def):
                    for leaf in self.sort_leaves(path_, modifier):
                        terms.append(sort_(leaf, order))

        if len(terms) > 0:
            return builder.sort(*terms)
        return builder

    def page_window(self) -> Tuple[int, int]:
        """``(limit, offset)`` of the current page; ``_maxresults`` caps the
        matches over all pages."""
        count = self.result_params.get("_count", DEFAULT_RESULT_COUNT)
        offset = 0
        if "page" in self.result_params and "_count" in self.result_params:
            offset = (self.result_params["page"] - 1) * count
        maxresults = self.result_params.get("_maxresults")
        if maxresults is not None:
            count = max(0, min(count, maxresults - offset))
        return count, offset

    def attach_limit_terms(self, builder):
        """ """
        limit, offset = self.page_window()
        return builder.limit(limit, offset)

    def elements_of(self, resource_type: str) -> Optional[List[str]]:
        """``_elements`` names for a resource type: plain names apply to the
        matches, ``Type.name`` to the resources of that type (matches and
        includes). ``None`` when the type is not subsetted."""
        names = self.result_params.get("_elements")
        if not names:
            return None
        selected = []
        for name in names:
            if "." in name:
                prefix, _, element = name.partition(".")
                if prefix == resource_type:
                    selected.append(element)
            elif resource_type in self.context.resource_types:
                selected.append(name)
        return selected or None

    def element_names(self, resource_type: str, names: List[str]) -> List[str]:
        """JSON names of the elements to return: the requested ones (a choice
        element stands for all its typed names; unknown names are ignored),
        plus ``id``, the mandatory and the modifier elements."""
        known = subsetting_elements(resource_type, self.context.engine.fhir_release)
        result = ["id"]
        for name in [*names, *known["mandatory"], *known["modifier"]]:
            for json_name in known["names"].get(name, []):
                if json_name not in result:
                    result.append(json_name)
        return result

    def attach_elements_terms(self, builder):
        """ """
        if "_elements" not in self.result_params:
            return builder
        if any(
            self.result_params.get(name)
            for name in ("_include", "_revinclude", "_graph")
        ):
            # the includes need the references: subsetted after (subset_results)
            return builder
        selected = {t: self.elements_of(t) for t in self.context.resource_types}
        if not any(selected.values()):
            # only other types (includes) are subsetted
            return builder

        paths = []
        for resource_type, names in selected.items():
            if names is None:
                # this type is returned whole
                paths.append(resource_type)
                continue
            paths.extend(
                f"{resource_type}.{name}"
                for name in self.element_names(resource_type, names)
            )
        return builder.element(*paths)

    def attach_summary_terms(self, builder):
        """ """
        if "_summary" not in self.result_params:
            return builder

        if self.result_params["_summary"] in ["count", "false"]:
            return builder

        specs = [
            lookup_fhir_resource_spec(r, True, self.context.engine.fhir_release)
            for r in self.context.resource_types
        ]

        if self.result_params["_summary"] in ("data", "true"):

            summary_elements = [
                f"{r}.{attr}"
                for r in self.context.resource_types
                for attr in ["id", "meta"]
            ]

            def should_include(attr):
                if self.result_params["_summary"] == "data":
                    return (
                        not attr.path.endswith(".text")
                        and not attr.is_main_profile_element
                    )
                elif self.result_params["_summary"] == "true":
                    return attr.is_summary

            # filter all summary attributes
            summary_attributes = [
                attr for spec in specs for attr in spec.elements if should_include(attr)
            ]

            def get_attr_paths(attribute):
                if attribute.path.endswith("[x]"):
                    for prop in attribute.as_properties():
                        return [
                            f"{prop.path.rsplit('.', 1)[0]}.{prop.name}"
                            for prop in attribute.as_properties()
                        ]
                else:
                    return [attribute.path]

            # append summary attributes' paths to summary_elements
            summary_elements.extend(
                [path for attr in summary_attributes for path in get_attr_paths(attr)]
            )

            return builder.element(*summary_elements)

        if self.result_params["_summary"] == "text":
            text_elements = [
                el.path
                for spec in specs
                for el in spec.elements
                if el.n_min is not None and el.n_min > 0
            ]
            text_elements.extend(
                [
                    f"{r}.{attr}"
                    for r in self.context.resource_types
                    for attr in ["text", "id", "meta"]
                ]
            )

            return builder.element(*text_elements)

    def response(self, result, includes, as_json):
        """The searchset Bundle: subsetted resources are tagged ``SUBSETTED``,
        ``_total=none`` leaves the total out, ``_score=true`` adds the
        relevance of each match."""
        self.subset_results(result, includes)
        bundle = self.context.engine.wrapped_with_bundle(
            result,
            includes=includes,
            as_json=True,
            applied_params=self.applied_params,
            outcome_issues=self.outcome_issues(),
        )
        if self.result_params.get("_total") == "none":
            bundle.pop("total", None)
        if self.result_params.get("_score"):
            self.attach_scores(bundle, result)
        if as_json:
            return bundle
        model = lookup_fhir_class("Bundle", fhir_release=self.context.engine.fhir_release)
        return model.model_validate(bundle)

    def subset_results(self, result, includes):
        """Tag the resources returned with only some of their elements; apply
        type-prefixed ``_elements`` to included resources."""
        summary = self.result_params.get("_summary") in ("true", "text", "data")
        for row in result.body:
            resource_type = row_key(row)[0]
            names = self.elements_of(resource_type)
            if names is not None and isinstance(row[0], dict):
                row[0] = subset_resource(
                    row[0], self.element_names(resource_type, names)
                )
            if summary or names is not None:
                tag_subsetted(row[0])
        if "_elements" not in self.result_params:
            return
        for include in includes:
            for row in include.body:
                resource_type = row_key(row)[0]
                names = self.elements_of(resource_type)
                if names is None or not isinstance(row[0], dict):
                    continue
                row[0] = subset_resource(
                    row[0], self.element_names(resource_type, names)
                )
                tag_subsetted(row[0])

    @staticmethod
    def attach_scores(bundle, result):
        """``entry.search.score`` (0..1, relative to the best match)."""
        scores = [getattr(row, "score", None) for row in result.body]
        if not scores or any(score is None for score in scores):
            return
        best = max(scores)
        matches = [
            e for e in bundle.get("entry", []) if e["search"]["mode"] == "match"
        ]
        for entry, score in zip(matches, scores):
            entry["search"]["score"] = round(score / best, 4) if best > 0 else 1.0

    def outcome_issues(self) -> List[Dict[str, Any]]:
        """Warnings for the Bundle's ``outcome`` entry: the ignored unknown
        search parameters and the warnings of the search."""
        issues = [
            {
                "severity": "warning",
                "code": "not-supported",
                "diagnostics": f"Unknown search parameter ``{name}`` was ignored.",
            }
            for name in self.ignored_params
        ]
        issues.extend(
            {"severity": "warning", "code": code, "diagnostics": message}
            for code, message in self.warnings
        )
        issues.extend(
            {"severity": "warning", "code": "processing", "diagnostics": message}
            for message in self.context.warnings
        )
        return issues

    def warn(self, message: str, code: str = "processing"):
        """Add a warning to the Bundle's outcome entry."""
        if (code, message) not in self.warnings:
            self.warnings.append((code, message))

    def execute(
        self,
    ) -> Generator[Any, EngineResult, Optional[Tuple[EngineResult, List]]]:
        """Run the search: resolve what the main query depends on (``_has``,
        hierarchies, chains), run it, then the includes. Yields the queries to
        run (``Search`` and ``AsyncSearch`` drive it); returns ``(matches,
        includes)``, or ``None`` when nothing can match."""
        # reverse chaining (_has)
        if self.result_params.get("_has"):
            self.reverse_chaining_results = yield from self.reverse_chains()
            # no resource satisfies the _has parameters, so nothing can match
            if not self.reverse_chaining_results:
                return None

        # reference hierarchies (:below / :above)
        for name in self.hierarchy_params():
            self.hierarchy_references[name] = yield from self.resolve_hierarchy(name)

        # chaining
        self.chained_references = []
        for param_name, value in self.chain_params:
            references = yield from self.chain(param_name, value)
            # no target satisfies the chain, so nothing can match
            if not references:
                return None
            self.chained_references.append(
                (self.chain_reference_name(param_name), references)
            )

        # MAIN QUERY
        if self.result_params.get("_summary") == "count":
            self.main_query = self.build()
            main_result = yield CountQuery(self.main_query)
        elif any("." in name for name, _, _ in self.sort_fields()):
            main_result = yield from self.chained_sort_page()
        else:
            self.main_query = self.build()
            main_result = yield self.main_query
        assert main_result is not None

        # _include / _revinclude / _graph
        includes = yield from self.resolve_includes(main_result)
        return main_result, includes

    def __call__(self, as_json=False):
        """ """
        outcome = run_chain_resolver(self.execute())
        if outcome is None:
            return self.empty_response(as_json)
        return self.response(*outcome, as_json)

    # ----------------------------------------------------------- chained sort

    def chained_sort_page(self) -> Generator[Any, EngineResult, EngineResult]:
        """``_sort`` by a chained parameter (``subject:Patient.name``), which
        Elasticsearch cannot sort on: every match is fetched and sorted in
        memory, then the page is cut out."""
        builder = Q_(self.context.resource_types, self.context.engine)
        builder = self.attach_where_terms(builder)
        builder = self.apply_resolved_terms(builder)
        everything = yield builder(unrestricted=self.context.unrestricted)
        rows = list(everything.body)

        keys: List[List[Any]] = [[] for _ in rows]
        for name, modifier, order in self.sort_fields():
            values = yield from self.sort_values(name, rows)
            for row_keys, value in zip(keys, values):
                row_keys.append((value, order))

        def sort_key(item):
            index, _ = item
            parts = []
            for value, order in keys[index]:
                missing = value is None
                parts.append(SortKey(value, order == SortOrderType.DESC, missing))
            return parts

        ordered = [row for _, row in sorted(enumerate(rows), key=sort_key)]
        limit, offset = self.page_window()
        page = ordered[offset : offset + limit]
        body = EngineResultBody()
        for row in page:
            body.append(row)
        return EngineResult(EngineResultHeader(total=len(rows)), body)

    def sort_values(self, name: str, rows) -> Generator[Any, EngineResult, List]:
        """The value each row sorts on for ``name`` (a parameter, or a chain
        ``ref[:Type].param``, resolved with sub-queries)."""
        links = name.split(".")
        resources = [row[0] for row in rows]
        context = self.context
        for link in links[:-1]:
            ref_name, target_type = self.parse_chain_link(link)
            targets: List[Optional[Tuple[str, str]]] = []
            wanted: Dict[str, Set[str]] = {}
            for resource in resources:
                reference = None
                if resource is not None:
                    params = context._get_search_param_definitions(ref_name)
                    for sp in params:
                        if sp.type != "reference":
                            raise ValidationError(
                                f"``_sort={name}``: {ref_name} is not a reference"
                            )
                        found = single_row_references(resource, sp)
                        for resource_type, ids in found.items():
                            if target_type in (None, resource_type) and ids:
                                reference = (resource_type, ids[0])
                                break
                        if reference:
                            break
                targets.append(reference)
                if reference:
                    wanted.setdefault(reference[0], set()).add(reference[1])
            fetched: Dict[Tuple[str, str], Any] = {}
            for resource_type, ids in sorted(wanted.items()):
                target_context = SearchContext(self.context.engine, resource_type)
                terms: List = []
                self.add_term(
                    target_context.normalize_param("_id", [",".join(sorted(ids))]),
                    terms,
                )
                result = yield Q_(resource_type, self.context.engine).where(*terms)(
                    unrestricted=self.context.unrestricted
                )
                for row in result.body:
                    fetched[row_key(row)] = row[0]
            resources = [fetched.get(t) if t else None for t in targets]
            types = {t[0] for t in targets if t}
            if len(types) > 1 and target_type is None:
                raise ValidationError(
                    f"``_sort={name}``: the chain may point to "
                    f"{', '.join(sorted(types))}; restrict it with ``:[type]``."
                )
            if not types:
                return [None for _ in rows]
            context = SearchContext(self.context.engine, types.pop())
        param = links[-1]
        values = []
        for resource in resources:
            if resource is None:
                values.append(None)
                continue
            sp = context._get_search_param_definitions(param)[0]
            values.append(sortable_value(resource, sp))
        return values

    def apply_resolved_terms(self, builder):
        """The ``_has`` and chain restrictions (see ``build``)."""
        if self.reverse_chaining_results:
            terms: List = []
            for resource_type, ids in self.reverse_chaining_results.items():
                search_context = SearchContext(self.context.engine, resource_type)
                for normalized_data in search_context.normalize_param(
                    "_id", [",".join(sorted(ids))]
                ):
                    self.add_term(normalized_data, terms)
            if len(terms) > 1:
                terms = [G_(*terms, path=terms[0].path, type_=GroupType.DECOUPLED)]
            builder = builder.where(*terms)
        for ref_name, references in self.chained_references:
            terms = []
            for normalized_data in self.context.normalize_param(
                ref_name, [",".join(references)]
            ):
                self.add_term(normalized_data, terms)
            builder = builder.where(*terms)
        return builder


class CountQuery:
    """A query run as a count (``_summary=count``)."""

    def __init__(self, query):
        self.query = query

    def fetchall(self):
        return self.query.count_raw()


class SortKey:
    """Orders values (strings case-insensitively); missing values last."""

    __slots__ = ("value", "reverse", "missing")

    def __init__(self, value, reverse, missing):
        if isinstance(value, str):
            value = value.casefold()
        self.value = value
        self.reverse = reverse
        self.missing = missing

    def __eq__(self, other):
        return self.missing == other.missing and self.value == other.value

    def __lt__(self, other):
        if self.missing or other.missing:
            return not self.missing and other.missing
        try:
            less = self.value < other.value
            greater = self.value > other.value
        except TypeError:
            less = str(self.value) < str(other.value)
            greater = str(self.value) > str(other.value)
        return greater if self.reverse else less


def single_row_references(resource, search_param) -> Dict[str, List[str]]:
    body = EngineResultBody()
    row = EngineResultRow()
    row.append(resource)
    body.append(row)
    return EngineResult(EngineResultHeader(total=1), body).extract_references(
        search_param
    )


# priority of the parts of a complex value when sorting
SORT_VALUE_KEYS = (
    "family",
    "given",
    "text",
    "value",
    "code",
    "display",
    "start",
    "reference",
    "city",
)


def sortable_value(resource, search_param):
    """First value of a parameter's expression on a resource, reduced to a
    primitive (a HumanName to its family name...)."""
    if not search_param.expression:
        return None
    try:
        values = fhirpath_compile(search_param.expression).evaluate(
            resource, resolver=resolve_literal_reference
        )
    except Exception:  # an expression the core engine can't evaluate here
        return None

    def reduce(value):
        while isinstance(value, (list, tuple)):
            if not value:
                return None
            value = value[0]
        if isinstance(value, dict):
            for key in SORT_VALUE_KEYS:
                if key in value:
                    return reduce(value[key])
            if "coding" in value:
                return reduce(value["coding"])
            return None
        return value

    for value in values:
        reduced = reduce(value)
        if reduced is not None:
            return str(reduced) if not isinstance(reduced, (int, float)) else reduced
    return None


class AsyncSearch(Search):
    """ """

    async def __call__(self, as_json=False):
        """ """
        outcome = await run_chain_resolver_async(self.execute())
        if outcome is None:
            return self.empty_response(as_json)
        return self.response(*outcome, as_json)


def fhir_search(
    context: SearchContext,
    query_string: str = None,
    params: Union[Dict[str, str], Tuple[Tuple[str, str]]] = None,
    response_as_dict: bool = False,
    handling: str = HANDLING_LENIENT,
):
    """``handling``: ``strict`` rejects unknown search parameters, ``lenient``
    (default) ignores them; ``handling_from_prefer`` reads it from the
    ``Prefer`` header."""
    if TYPE_CHECKING:
        klass: Union[Type[AsyncSearch], Type[Search]]
    if context.engine.__class__.is_async():
        klass = AsyncSearch
    else:
        klass = Search
    factory = klass(
        context, query_string=query_string, params=params, handling=handling
    )
    return factory(as_json=response_as_dict)
