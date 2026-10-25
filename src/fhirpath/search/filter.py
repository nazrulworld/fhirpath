# _*_ coding: utf-8 _*_
"""``_filter`` (https://hl7.org/fhir/R5/search_filter.html): parsing and
translation into FQL terms.

::

    filter    = paramExp / logExp / ("not") "(" filter ")"
    logExp    = filter ("and" / "or" filter)+        ; no precedence: left to right
    paramExp  = paramPath SP compareOp SP compValue
    paramPath = paramName (("[" filter "]") "." paramPath) / paramName "." paramPath
              / "_has:" type ":" param ":" paramPath

Comparisons are made of the context's search parameters: ``name co "pet"``,
``subject.name sw "pe"`` (chains), ``subject[gender eq male].name sw "pe"`` (a
chain filtered on the target), ``_has:Observation:patient:code eq 1234-5``
(reverse chains).
"""
import json
import re
from typing import Any, List, NamedTuple, Optional, Union

from fhirpath.enums import GroupType
from fhirpath.search.exceptions import ValidationError
from fhirpath.search.fql import G_

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

COMPARE_OPERATORS = (
    "eq",
    "ne",
    "co",
    "sw",
    "ew",
    "gt",
    "lt",
    "ge",
    "le",
    "ap",
    "sa",
    "eb",
    "pr",
    "po",
    "ss",
    "sb",
    "in",
    "ni",
    "re",
)
# shorthand system names
SYSTEM_ALIASES = {
    "loinc": "http://loinc.org",
    "snomed": "http://snomed.info/sct",
    "rxnorm": "http://www.nlm.nih.gov/research/umls/rxnorm",
    "ucum": "http://unitsofmeasure.org",
}
PREFIX_OPERATORS = ("gt", "lt", "ge", "le", "ap", "sa", "eb")
RANGED_TYPES = ("number", "date", "quantity")


class FilterSyntaxError(ValidationError):
    """A ``_filter`` that does not follow the grammar."""


# ------------------------------------------------------------------ the tree


class Comparison(NamedTuple):
    path: "ParamPath"
    operator: str
    value: str
    quoted: bool


class ParamPath(NamedTuple):
    """``name``, ``name[filter].next`` or ``name.next``; ``has`` holds the
    ``_has:Type:param`` prefix of a reverse chain."""

    name: str
    filter: Optional[Any] = None
    next: Optional["ParamPath"] = None
    has: Optional[str] = None


class Logical(NamedTuple):
    operator: str  # and / or
    left: Any
    right: Any


class Not(NamedTuple):
    operand: Any


Node = Union[Comparison, Logical, Not]


# --------------------------------------------------------------- the parser

TOKEN = re.compile(
    r"""\s*(?:
        (?P<string>"(?:[^"\\]|\\.)*")
      | (?P<open>\()
      | (?P<close>\))
      | (?P<lbracket>\[)
      | (?P<rbracket>\])
      | (?P<word>[^\s()\[\]"]+)
    )""",
    re.X,
)


def tokenize(text: str):
    tokens = []
    position = 0
    text = text.strip()
    while position < len(text):
        match = TOKEN.match(text, position)
        if match is None or match.end() == position:
            raise FilterSyntaxError(f"_filter: unexpected input at {text[position:]!r}")
        kind = match.lastgroup
        tokens.append((kind, match.group(kind)))
        position = match.end()
    return tokens


class Parser:
    def __init__(self, text: str):
        self.text = text
        self.tokens = tokenize(text)
        self.position = 0

    def peek(self, offset=0):
        index = self.position + offset
        return self.tokens[index] if index < len(self.tokens) else (None, None)

    def take(self, kind=None, value=None):
        token = self.peek()
        if token[0] is None:
            raise FilterSyntaxError(f"_filter: unexpected end of {self.text!r}")
        if (kind and token[0] != kind) or (value and token[1].lower() != value):
            raise FilterSyntaxError(
                f"_filter: expected {value or kind}, got {token[1]!r} in {self.text!r}"
            )
        self.position += 1
        return token

    def parse(self) -> Node:
        node = self.expression()
        if self.peek()[0] is not None:
            raise FilterSyntaxError(
                f"_filter: unexpected {self.peek()[1]!r} in {self.text!r}"
            )
        return node

    def expression(self, closing=None) -> Node:
        node = self.unit()
        while True:
            kind, value = self.peek()
            if kind is None or kind == closing:
                return node
            if kind == "word" and value.lower() in ("and", "or"):
                self.position += 1
                # left to right: no precedence
                node = Logical(value.lower(), node, self.unit())
                continue
            raise FilterSyntaxError(f"_filter: expected and/or, got {value!r}")

    def unit(self) -> Node:
        kind, value = self.peek()
        if kind == "word" and value.lower() == "not" and self.peek(1)[0] == "open":
            self.position += 2
            node = self.expression("close")
            self.take("close")
            return Not(node)
        if kind == "open":
            self.position += 1
            node = self.expression("close")
            self.take("close")
            return node
        return self.comparison()

    def comparison(self) -> Comparison:
        path = self.param_path()
        kind, operator = self.take("word")
        operator = operator.lower()
        if operator not in COMPARE_OPERATORS:
            raise FilterSyntaxError(f"_filter: unknown operator {operator!r}")
        kind, value = self.take()
        if kind == "string":
            return Comparison(path, operator, json.loads(value), True)
        if kind != "word":
            raise FilterSyntaxError(f"_filter: missing value after {operator!r}")
        return Comparison(path, operator, value, False)

    def param_path(self) -> ParamPath:
        kind, word = self.take("word")
        has = None
        if word.startswith("_has:"):
            parts = word.split(":")
            if len(parts) != 4 or not all(parts):
                raise FilterSyntaxError(
                    f"_filter: bad reverse chain {word!r} (_has:Type:param:param)"
                )
            has = ":".join(parts[:3])
            word = parts[3]
        name, dot, rest = word.partition(".")
        filter_ = None
        if not dot and self.peek()[0] == "lbracket":
            self.position += 1
            filter_ = self.expression("rbracket")
            self.take("rbracket")
            kind, rest = self.take("word")
            if not rest.startswith("."):
                raise FilterSyntaxError("_filter: expected '.' after a [filter]")
            rest, dot = rest[1:], "."
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_\-]*$", name):
            raise FilterSyntaxError(f"_filter: bad parameter name {name!r}")
        next_ = None
        if dot:
            if not rest:
                raise FilterSyntaxError(f"_filter: incomplete path {word!r}")
            # the rest of the path is parsed again (it may hold a [filter])
            self.tokens.insert(self.position, ("word", rest))
            next_ = self.param_path()
        return ParamPath(name, filter_, next_, has)


def parse_filter(text: str) -> Node:
    return Parser(text).parse()


# ------------------------------------------------------------- translation


def escape_search_value(value: str, keep: str = "") -> str:
    """A filter value as a search value: ``,`` ``$`` ``|`` ``\\`` escaped,
    except the separators in ``keep``."""
    return "".join(
        "\\" + c if c in ",$|\\" and c not in keep else c for c in value
    )


def expand_aliases(value: str) -> str:
    """``loinc|1234-5`` -> ``http://loinc.org|1234-5``; ``5|ucum|mg``."""
    parts = value.split("|")
    return "|".join(SYSTEM_ALIASES.get(p, p) for p in parts)


def comparison_param(search_param, comparison: Comparison):
    """``(name suffix, value)`` of a comparison on ``search_param``: the
    modifier (``:contains``...) and the value (with a prefix)."""
    operator, value = comparison.operator, comparison.value
    type_ = search_param.type
    if type_ == "composite":
        if operator not in ("eq", "ne"):
            raise ValidationError(
                f"_filter: only eq and ne apply to composite {search_param.code}"
            )
        return ("" if operator == "eq" else None), composite_value(search_param, value)

    if operator == "pr":
        if value not in ("true", "false"):
            raise ValidationError("_filter: pr takes true or false")
        return ":missing", "false" if value == "true" else "true"

    if type_ in ("token", "quantity", "reference", "uri"):
        searched = escape_search_value(expand_aliases(value), keep="|")
    else:
        searched = escape_search_value(value)

    if type_ == "string":
        modifiers = {"eq": ":_eq_ci", "ne": ":not", "co": ":contains", "sw": "", "ew": ":_ew"}
        if operator in modifiers:
            return modifiers[operator], searched
    elif type_ in RANGED_TYPES:
        if operator in ("eq", "co"):
            return "", searched
        if operator in ("ne", *PREFIX_OPERATORS):
            return "", operator + searched
        if operator == "po" and type_ == "date":
            return "po", searched
    elif type_ == "token":
        modifiers = {
            "eq": "",
            "ne": ":not",
            "ss": ":above",
            "sb": ":below",
            "in": ":in",
            "ni": ":not-in",
        }
        if operator in modifiers:
            return modifiers[operator], searched
    elif type_ in ("reference", "uri"):
        modifiers = {"eq": "", "re": "", "ne": ":not", "sw": ":below", "ss": ":above", "sb": ":below"}
        if type_ == "uri":
            modifiers["co"] = ":contains"
        if operator in modifiers:
            return modifiers[operator], searched
    raise ValidationError(
        f"_filter: operator {operator} does not apply to {type_} parameter "
        f"{search_param.code}"
    )


def composite_value(search_param, value: str) -> str:
    """``code$loinc|12907-2,value$ge150|ucum|mmol/L`` -> the ``$`` tuple in the
    order of the composite's components."""
    named = {}
    for part in value.split(","):
        name, sep, component_value = part.partition("$")
        if not sep:
            raise ValidationError(
                f"_filter: composite values are name$value pairs, got {part!r}"
            )
        named[name] = expand_aliases(component_value)
    ordered = []
    for component in search_param.component or []:
        definition = component.get("definition")
        if isinstance(definition, dict):
            definition = definition.get("reference")
        code = (definition or "").rsplit("/", 1)[-1].split("-", 1)[-1]
        match = [n for n in named if code.endswith(n) or n == code]
        if not match:
            raise ValidationError(
                f"_filter: composite {search_param.code} misses component {code}"
            )
        ordered.append(named.pop(match[0]))
    return "$".join(ordered)


def compile_filter(search, context, node: Node):
    """Terms of ``node`` on the resources of ``context`` (generator: chains
    and reverse chains are resolved with sub-queries). Returns a list of
    terms; an empty OR group when nothing can match."""
    if isinstance(node, Logical):
        left = yield from compile_filter(search, context, node.left)
        right = yield from compile_filter(search, context, node.right)
        terms = [*left, *right]
        if node.operator == "and":
            return [G_(*terms, path=None, type_=GroupType.COUPLED)]
        group = G_(
            *[_single(t) for t in (left, right)], path=None, type_=GroupType.DECOUPLED
        )
        return [group.match_any()]
    if isinstance(node, Not):
        inner = yield from compile_filter(search, context, node.operand)
        return [G_(_single(inner), path=None, type_=GroupType.DECOUPLED).match_no_one()]
    terms = yield from compile_comparison(search, context, node.path, node)
    return terms


def _single(terms):
    if len(terms) == 1:
        return terms[0]
    return G_(*terms, path=None, type_=GroupType.COUPLED)


def nothing():
    """A term no resource matches."""
    return G_(path=None, type_=GroupType.DECOUPLED).match_any()


def compile_comparison(search, context, path: ParamPath, comparison: Comparison):
    from fhirpath.search.search import SearchContext

    if path.has is not None:
        # _has:Type:param:<path>: the context resources referred to by matching
        # sources
        _, source_type, ref_name = path.has.split(":")
        source_context = SearchContext(
            context.engine, source_type, unrestricted=context.unrestricted
        )
        (resource_type,) = context.resource_types
        ref_param = search._has_reference_param(source_context, ref_name, resource_type)
        source_terms = yield from compile_comparison(
            search, source_context, ParamPath(path.name, path.filter, path.next), comparison
        )
        from fhirpath.search.query import Q_

        result = yield Q_(source_type, context.engine).where(*source_terms)(
            unrestricted=context.unrestricted
        )
        ids = result.extract_references(ref_param).get(resource_type, [])
        if not ids:
            return [nothing()]
        terms = []
        search.add_term(context.normalize_param("_id", [",".join(dict.fromkeys(ids))]), terms)
        return terms

    name = path.name
    if name == "id" and not _defines(context, "id"):
        name = "_id"

    if path.next is not None:
        # a chain: the targets that satisfy the rest (and the [filter])
        references = yield from resolve_chain(search, context, name, path, comparison)
        if not references:
            return [nothing()]
        terms = []
        search.add_term(context.normalize_param(name, [",".join(references)]), terms)
        return terms

    search_params = context._get_search_param_definitions(name)
    terms: List = []
    for search_param in search_params:
        suffix, value = comparison_param(search_param, comparison)
        if suffix is None:
            # composite ne
            positive = []
            search.add_term(context.normalize_param(name, [value]), positive)
            terms.append(G_(*positive, path=None, type_=GroupType.DECOUPLED).match_no_one())
        elif suffix == "po":
            # the period overlaps the value's range: ge and le together
            for prefix in ("ge", "le"):
                search.add_term(context.normalize_param(name, [prefix + value]), terms)
        else:
            search.add_term(context.normalize_param(name + suffix, [value]), terms)
        break
    return terms


def _defines(context, name) -> bool:
    return all(getattr(d, name, None) is not None for d in context.definitions)


def resolve_chain(search, context, name, path: ParamPath, comparison):
    """``Type/id`` references of the targets of reference parameter ``name``
    that satisfy the rest of the path (and the bracket filter)."""
    from fhirpath.search.query import Q_
    from fhirpath.search.search import SearchContext, reference_targets

    ref_name, _, target_type = name.partition(":")
    ref_params = context._get_search_param_definitions(ref_name)
    targets: List[str] = []
    for ref_param in ref_params:
        if ref_param.type != "reference":
            raise ValidationError(
                f"_filter: {ref_name} is not a reference parameter, it cannot be chained"
            )
        targets.extend(t for t in reference_targets(ref_param) if t not in targets)
    if target_type:
        targets = [target_type]
    next_name = path.next.name if path.next.has is None else None
    if next_name:
        next_code = "_id" if next_name == "id" else next_name
        targets = [
            t for t in targets if search._defines_search_param(t, next_code)
        ] or targets

    references: List[str] = []
    for resource_type in targets:
        target_context = SearchContext(
            context.engine, resource_type, unrestricted=context.unrestricted
        )
        try:
            terms = yield from compile_comparison(
                search, target_context, path.next, comparison
            )
            if path.filter is not None:
                filter_terms = yield from compile_filter(
                    search, target_context, path.filter
                )
                terms = [*terms, *filter_terms]
        except (ValidationError, NotImplementedError, KeyError, AttributeError):
            # a target type the rest of the path does not apply to
            if len(targets) == 1:
                raise
            continue
        result = yield Q_(resource_type, context.engine).where(*terms)(
            unrestricted=context.unrestricted
        )
        references.extend(
            f"{resource_type}/{id_}"
            for id_ in result.extract_ids().get(resource_type, [])
        )
    return references
