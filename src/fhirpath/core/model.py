# _*_ coding: utf-8 _*_
"""FHIR data navigation for the FHIRPath engine.

Resources can be given as ``fhir.resources`` (pydantic, ``fhir_core``) model
instances or as plain JSON-like dicts (``json.loads(..., parse_float=Decimal)``
keeps decimal precision). Type information always comes from the
``fhir.resources`` model classes, so both forms navigate identically:

* choice elements are reached by their base name (``Observation.value``);
* primitive extensions (``_birthDate`` / ``birthDate__ext``) are attached to the
  primitive node, which therefore has ``id``/``extension`` children;
* every node knows its FHIR type name, parent and position (for ``pathname()``).
"""

import base64
import datetime
import typing
import uuid
from decimal import Decimal
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fhir_core.fhirabstractmodel import FHIRAbstractModel

from .types import FPDate, FPDateTime, FPTime, Long, Quantity

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

UCUM_SYSTEM = "http://unitsofmeasure.org"

#: fhir_core primitive annotation metadata class name -> FHIR primitive type
_PRIMITIVE_META = {
    "Boolean": "boolean",
    "String": "string",
    "Code": "code",
    "Id": "id",
    "Uri": "uri",
    "Url": "url",
    "Canonical": "canonical",
    "Oid": "oid",
    "Uuid": "uuid",
    "UuidVersion": "uuid",
    "Markdown": "markdown",
    "Base64Binary": "base64Binary",
    "EncodedBytes": "base64Binary",
    "Xhtml": "xhtml",
    "Integer": "integer",
    "UnsignedInt": "unsignedInt",
    "PositiveInt": "positiveInt",
    "Integer64": "integer64",
    "Decimal": "decimal",
    "Date": "date",
    "DateTime": "dateTime",
    "Instant": "instant",
    "Time": "time",
}

PRIMITIVE_TYPES = frozenset(_PRIMITIVE_META.values())

#: FHIR primitive -> its FHIR base primitive (StructureDefinition.baseDefinition)
PRIMITIVE_PARENTS = {
    "code": "string",
    "id": "string",
    "markdown": "string",
    "url": "uri",
    "canonical": "uri",
    "oid": "uri",
    "uuid": "uri",
    "unsignedInt": "integer",
    "positiveInt": "integer",
}

STRING_LIKE = frozenset(
    {
        "string",
        "code",
        "id",
        "uri",
        "url",
        "canonical",
        "oid",
        "uuid",
        "markdown",
        "base64Binary",
        "xhtml",
    }
)
INTEGER_LIKE = frozenset({"integer", "unsignedInt", "positiveInt"})
QUANTITY_TYPES = frozenset(
    {
        "Quantity",
        "Age",
        "Count",
        "Distance",
        "Duration",
        "SimpleQuantity",
        "MoneyQuantity",
    }
)

#: FHIR Quantity UCUM time codes that map to calendar durations (FHIR spec)
UCUM_TO_CALENDAR = {
    "a": "year",
    "mo": "month",
    "wk": "week",
    "d": "day",
    "h": "hour",
    "min": "minute",
    "s": "second",
    "ms": "millisecond",
}

_SKIP_FIELDS = frozenset({"fhir_comments", "resource_type"})


# ---------------------------------------------------------------------------
# model metadata
# ---------------------------------------------------------------------------


class FieldMeta:
    __slots__ = ("attr", "json_name", "is_list", "type_name", "klass", "choice_of")

    def __init__(self, attr, json_name, is_list, type_name, klass, choice_of):
        self.attr = attr
        self.json_name = json_name
        self.is_list = is_list
        self.type_name = type_name  # None -> resolve from the value (Resource)
        self.klass = klass
        self.choice_of = choice_of

    @property
    def is_primitive(self) -> bool:
        return self.type_name in PRIMITIVE_TYPES


def _unwrap(annotation) -> Tuple[bool, Any]:
    """-> (is_list, inner annotation) with Optional/Union[None] removed."""
    is_list = False
    while True:
        origin = typing.get_origin(annotation)
        if origin is typing.Union or (
            origin is not None and str(origin) == "<class 'types.UnionType'>"
        ):
            args = [a for a in typing.get_args(annotation) if a is not type(None)]
            annotation = args[0]
            continue
        if origin in (list, typing.List):
            is_list = True
            annotation = typing.get_args(annotation)[0]
            continue
        return is_list, annotation


def _type_from_annotation(annotation) -> Tuple[Optional[str], Optional[type]]:
    if typing.get_origin(annotation) is typing.Annotated:
        args = typing.get_args(annotation)
        for meta in args[1:]:
            name = _PRIMITIVE_META.get(type(meta).__name__)
            if name:
                return name, None
        base = args[0]
        if base is bool:
            return "boolean", None
        return "string", None
    if annotation is bool:
        return "boolean", None
    if annotation is str:
        return "string", None
    if annotation is Decimal:
        return "decimal", None
    if annotation is int:
        return "integer", None
    get_klass = getattr(annotation, "get_model_klass", None)
    if get_klass is not None:
        klass = get_klass()
        if klass.__name__ in ("Resource",) and annotation.__name__ == "ResourceType":
            return None, None
        return klass.get_resource_type(), klass
    return None, None


@lru_cache(maxsize=None)
def class_fields(
    klass: type,
) -> Tuple[Dict[str, FieldMeta], Dict[str, List[FieldMeta]]]:
    """-> (element name -> meta, choice base name -> metas) for a model class."""
    fields: Dict[str, FieldMeta] = {}
    choices: Dict[str, List[FieldMeta]] = {}
    for attr, info in klass.model_fields.items():
        if attr in _SKIP_FIELDS or attr.endswith("__ext"):
            continue
        extra = info.json_schema_extra or {}
        if not isinstance(extra, dict) or not extra.get("element_property", False):
            if attr != "id":
                continue
        is_list, inner = _unwrap(info.annotation)
        type_name, klass_ = _type_from_annotation(inner)
        json_name = info.alias or attr
        choice_of = extra.get("one_of_many") if isinstance(extra, dict) else None
        meta = FieldMeta(attr, json_name, is_list, type_name, klass_, choice_of)
        fields[json_name] = meta
        if choice_of:
            choices.setdefault(choice_of, []).append(meta)
    return fields, choices


@lru_cache(maxsize=None)
def lookup_class(type_name: str) -> Optional[type]:
    if not type_name:
        return None
    try:
        from fhir.resources import get_fhir_model_class

        return get_fhir_model_class(type_name)
    except (KeyError, ValueError, LookupError, ImportError):
        return None


def class_ancestors(klass: type) -> List[str]:
    """FHIR type names of the class and its FHIR supertypes (most specific first)."""
    names = []
    for base in klass.__mro__:
        if not (isinstance(base, type) and issubclass(base, FHIRAbstractModel)):
            continue
        if base is FHIRAbstractModel:
            continue
        try:
            name = base.get_resource_type()
        except Exception:  # noqa: B902
            continue
        if name and name not in names:
            names.append(name)
    return names


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


class Node:
    """A FHIR element in a FHIRPath collection.

    ``value`` is the raw data (model instance, dict, or a primitive Python
    value; ``None`` for a primitive that only has extensions); ``ext`` is the
    primitive's extension element (``_x`` / ``x__ext``).
    """

    __slots__ = (
        "value",
        "type_name",
        "klass",
        "name",
        "parent",
        "index",
        "ext",
        "_children",
    )

    def __init__(
        self,
        value: Any,
        type_name: Optional[str] = None,
        klass: Optional[type] = None,
        name: Optional[str] = None,
        parent: Optional["Node"] = None,
        index: Optional[int] = None,
        ext: Any = None,
    ):
        self.value = value
        self.name = name
        self.parent = parent
        self.index = index
        self.ext = ext
        self._children = None
        if isinstance(value, FHIRAbstractModel):
            # keep a declared class the value does not specialise (e.g. the
            # FHIRPrimitiveExtension holder of a primitive's id/extension)
            if klass is None or issubclass(type(value), klass):
                klass = type(value)
                if type_name is None or _is_resource_class(klass):
                    type_name = klass.get_resource_type()
        elif isinstance(value, dict) and "resourceType" in value:
            type_name = value["resourceType"]
            klass = lookup_class(type_name)
        elif (
            klass is None and type_name is not None and type_name not in PRIMITIVE_TYPES
        ):
            klass = lookup_class(type_name)
        self.type_name = type_name
        self.klass = klass

    @classmethod
    def root(cls, resource: Any) -> "Node":
        return cls(resource)

    def __repr__(self):
        return "Node(%s %s=%r)" % (self.type_name, self.name, self.value)

    # -- identity --------------------------------------------------------------
    @property
    def is_primitive(self) -> bool:
        return self.type_name in PRIMITIVE_TYPES

    @property
    def is_resource(self) -> bool:
        return self.klass is not None and _is_resource_class(self.klass)

    def has_value(self) -> bool:
        return self.is_primitive and self.value is not None

    def type_names(self) -> List[str]:
        """Own FHIR type and FHIR supertypes, most specific first."""
        if self.is_primitive:
            names = [self.type_name]
            parent = PRIMITIVE_PARENTS.get(self.type_name)
            while parent:
                names.append(parent)
                parent = PRIMITIVE_PARENTS.get(parent)
            return names + ["PrimitiveType", "DataType", "Element", "Base"]
        if self.klass is not None:
            return class_ancestors(self.klass)
        return [self.type_name] if self.type_name else []

    def path(self, short: bool = False) -> str:
        parts = []
        node = self
        while node is not None:
            if node.parent is None:
                parts.append(node.type_name or "")
                break
            segment = node.name or ""
            if node.index is not None:
                segment += "[%d]" % node.index
            parts.append(segment)
            node = node.parent
        return ".".join(reversed(parts))

    def resource_node(self) -> Optional["Node"]:
        node = self
        while node is not None:
            if node.is_resource:
                return node
            node = node.parent
        return None

    # -- navigation --------------------------------------------------------------
    def child(self, name: str) -> List["Node"]:
        """Children named ``name`` (choice base names included)."""
        if self.is_primitive:
            return self._primitive_child(name)
        value = self.value
        if value is None:
            return []
        if self.klass is not None:
            fields, choices = class_fields(self.klass)
            meta = fields.get(name)
            if meta is not None:
                # typed choice names (valueQuantity) are accepted leniently, like fhirpath.js
                return self._make(meta, meta.choice_of or name)
            if name in choices:
                result = []
                for choice in choices[name]:
                    result.extend(self._make(choice, name))
                return result
            return []
        # untyped dict navigation
        if isinstance(value, dict):
            if name in value:
                return _untyped_nodes(value[name], name, self, value.get("_" + name))
            result = []
            for key, item in value.items():
                if key.startswith(name) and key[len(name) : len(name) + 1].isupper():
                    result.extend(
                        _untyped_nodes(item, name, self, value.get("_" + key))
                    )
            return result
        if hasattr(value, name):
            return _untyped_nodes(getattr(value, name), name, self, None)
        return []

    def children(self) -> List["Node"]:
        if self._children is not None:
            return self._children
        result: List[Node] = []
        if self.is_primitive:
            result.extend(self._primitive_child("id"))
            result.extend(self._primitive_child("extension"))
        elif self.klass is not None:
            fields, _ = class_fields(self.klass)
            for json_name, meta in fields.items():
                result.extend(self._make(meta, meta.choice_of or json_name))
        elif isinstance(self.value, dict):
            for key in self.value:
                if key.startswith("_") or key == "resourceType":
                    continue
                result.extend(self.child(key))
        self._children = result
        return result

    def _primitive_child(self, name: str) -> List["Node"]:
        if self.ext is None or name not in ("id", "extension"):
            return []
        holder = Node(self.ext, "Element", lookup_class("Element"), parent=self.parent)
        return [
            Node(n.value, n.type_name, n.klass, name, self, n.index, n.ext)
            for n in holder.child(name)
        ]

    def _make(self, meta: FieldMeta, element_name: str) -> List["Node"]:
        value, ext = self._raw(meta)
        if value is None and ext is None:
            return []
        type_name = meta.type_name
        if meta.choice_of:
            type_name = type_name or _choice_type(meta.json_name, meta.choice_of)
        if meta.is_list or isinstance(value, list) or isinstance(ext, list):
            values = (
                value if isinstance(value, list) else ([] if value is None else [value])
            )
            exts = ext if isinstance(ext, list) else []
            count = max(len(values), len(exts))
            nodes = []
            for index in range(count):
                item = values[index] if index < len(values) else None
                item_ext = exts[index] if index < len(exts) else None
                if item is None and item_ext is None:
                    continue
                nodes.append(
                    Node(
                        _coerce(item, type_name),
                        type_name,
                        meta.klass,
                        element_name,
                        self,
                        index,
                        item_ext,
                    )
                )
            return nodes
        return [
            Node(
                _coerce(value, type_name),
                type_name,
                meta.klass,
                element_name,
                self,
                None,
                ext,
            )
        ]

    def _raw(self, meta: FieldMeta):
        value = self.value
        if isinstance(value, FHIRAbstractModel):
            return getattr(value, meta.attr, None), getattr(
                value, meta.attr + "__ext", None
            )
        if isinstance(value, dict):
            return value.get(meta.json_name), value.get("_" + meta.json_name)
        return None, None

    # -- System conversion ---------------------------------------------------------
    def to_system(self) -> Any:
        """The System value of a primitive / Quantity node, else ``self``."""
        if self.is_primitive:
            return primitive_to_system(self.value, self.type_name)
        if self.type_name in QUANTITY_TYPES:
            return quantity_to_system(self)
        return self

    def get(self, name: str) -> Any:
        """Raw value of a direct child (first item), for internal use."""
        children = self.child(name)
        if not children:
            return None
        return children[0].to_system() if children[0].is_primitive else children[0]


def _is_resource_class(klass: type) -> bool:
    resource = lookup_class("Resource")
    return resource is not None and issubclass(klass, resource)


def _choice_type(json_name: str, base: str) -> Optional[str]:
    suffix = json_name[len(base) :]
    if not suffix:
        return None
    lowered = suffix[0].lower() + suffix[1:]
    if lowered in PRIMITIVE_TYPES:
        return lowered
    return suffix


def _coerce(value: Any, type_name: Optional[str]) -> Any:
    """Normalise JSON-mode numbers (floats) to Decimal for decimal elements."""
    if type_name == "decimal" and isinstance(value, float):
        return Decimal(repr(value))
    return value


def _untyped_nodes(value, name, parent, ext) -> List[Node]:
    if value is None:
        return []
    if isinstance(value, list):
        exts = ext if isinstance(ext, list) else []
        return [
            Node(
                item,
                _guess_type(item),
                None,
                name,
                parent,
                index,
                exts[index] if index < len(exts) else None,
            )
            for index, item in enumerate(value)
            if item is not None
        ]
    return [Node(value, _guess_type(value), None, name, parent, None, ext)]


def _guess_type(value) -> Optional[str]:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, (float, Decimal)):
        return "decimal"
    if isinstance(value, str):
        return "string"
    if isinstance(value, FHIRAbstractModel):
        return type(value).get_resource_type()
    if isinstance(value, dict) and "resourceType" in value:
        return value["resourceType"]
    return None


def primitive_to_system(value: Any, type_name: str) -> Any:
    """FHIR primitive value -> System value (``None`` when absent/unparseable)."""
    if value is None:
        return None
    if type_name == "boolean":
        return bool(value)
    if type_name in STRING_LIKE:
        if isinstance(value, bytes):
            return base64.b64encode(value).decode("ascii")
        if isinstance(value, uuid.UUID):
            return "urn:uuid:%s" % value
        return str(value)
    if type_name in INTEGER_LIKE:
        return int(value)
    if type_name == "integer64":
        return Long(int(value))
    if type_name == "decimal":
        if isinstance(value, Decimal):
            return value
        if isinstance(value, float):
            return Decimal(repr(value))
        return Decimal(str(value))
    if type_name == "date":
        if isinstance(value, datetime.date):
            return FPDate.from_python(value)
        return FPDate.parse(str(value))
    if type_name in ("dateTime", "instant"):
        if isinstance(value, datetime.datetime):
            return FPDateTime.from_python(value)
        if isinstance(value, datetime.date):
            return FPDateTime(value.year, value.month, value.day, precision=2)
        return FPDateTime.parse(str(value))
    if type_name == "time":
        if isinstance(value, datetime.time):
            return FPTime.from_python(value)
        return FPTime.parse(str(value))
    return value


def quantity_to_system(node: Node) -> Optional[Quantity]:
    value = node.get("value")
    if value is None:
        return None
    code = node.get("code")
    system = node.get("system")
    unit = node.get("unit")
    if code is not None and (system is None or system == UCUM_SYSTEM):
        unit_text = (
            UCUM_TO_CALENDAR.get(code, code)
            if system == UCUM_SYSTEM and code in ("a", "mo")
            else code
        )
    elif unit is not None:
        unit_text = unit
    else:
        unit_text = "1"
    return Quantity(Decimal(value), unit_text)


def iter_descendants(nodes: Iterable[Node]) -> Iterable[Node]:
    stack = list(nodes)
    while stack:
        node = stack.pop(0)
        for child in node.children():
            yield child
            stack.append(child)


__all__ = [
    "Node",
    "FieldMeta",
    "class_fields",
    "lookup_class",
    "primitive_to_system",
    "PRIMITIVE_TYPES",
    "PRIMITIVE_PARENTS",
    "QUANTITY_TYPES",
]
