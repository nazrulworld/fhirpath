# _*_ coding: utf-8 _*_
"""Value helpers shared by operators and functions: System conversion, singleton
evaluation, implicit conversions and the type system (``is``/``as``/``type()``)."""

from decimal import Decimal
from typing import Any, List, Optional, Tuple

from .evaluation import EvaluationError
from .model import PRIMITIVE_PARENTS, PRIMITIVE_TYPES, Node, lookup_class
from .types import FPDate, FPDateTime, FPTime, Long, Quantity, TypeInfo, TypeSpecifier

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

SYSTEM_TYPES = (
    "Any",
    "Boolean",
    "String",
    "Integer",
    "Long",
    "Decimal",
    "Date",
    "DateTime",
    "Time",
    "Quantity",
)


class Missing:
    """Marker for "no value" (an empty singleton)."""

    __slots__ = ()

    def __repr__(self):
        return "MISSING"

    def __bool__(self):
        return False


MISSING = Missing()


def system(item: Any) -> Any:
    """FHIR primitive/Quantity node -> System value; other items unchanged."""
    if isinstance(item, Node):
        value = item.to_system()
        return MISSING if value is None else value
    return item


def to_output(item: Any) -> Any:
    """Collection item -> public Python value (``None`` for a primitive without value)."""
    if isinstance(item, Node):
        if item.is_primitive:
            value = system(item)
            return None if value is MISSING else value
        return item.value
    return item


def system_collection(collection: List[Any]) -> List[Any]:
    result = []
    for item in collection:
        value = system(item)
        if value is not MISSING:
            result.append(value)
    return result


def singleton(
    collection: List[Any], what: str = "operand", expression: str = ""
) -> Any:
    """Singleton evaluation: ``MISSING`` for empty, the item for one, error for more."""
    if not collection:
        return MISSING
    if len(collection) > 1:
        raise EvaluationError(
            "%s must be a single item, got %d" % (what, len(collection)), expression
        )
    return collection[0]


def singleton_value(
    collection: List[Any], what: str = "operand", expression: str = ""
) -> Any:
    return system(singleton(collection, what, expression))


def singleton_boolean(
    collection: List[Any], what: str = "operand", expression: str = ""
) -> Any:
    """Singleton evaluation of collections for a Boolean context."""
    item = singleton(collection, what, expression)
    if item is MISSING:
        return MISSING
    value = system(item)
    if value is MISSING:
        return True  # a node without a value is still "a single item"
    if isinstance(value, bool):
        return value
    return True


def is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value: Any) -> bool:
    return is_integer(value) or isinstance(value, Decimal)


def is_string(value: Any) -> bool:
    return isinstance(value, str)


def as_decimal(value: Any) -> Optional[Decimal]:
    if isinstance(value, Decimal):
        return value
    if is_integer(value):
        return Decimal(int(value))
    return None


def as_quantity(value: Any) -> Optional[Quantity]:
    if isinstance(value, Quantity):
        return value
    if is_number(value):
        return Quantity(as_decimal(value), "1")
    return None


def promote(left: Any, right: Any) -> Tuple[Any, Any]:
    """Implicit conversions so both operands share a type where the spec allows it.

    Integer -> Long -> Decimal -> Quantity, Date -> DateTime.
    """
    if type(left) is type(right):
        return left, right
    if is_number(left) and is_number(right):
        if isinstance(left, Decimal) or isinstance(right, Decimal):
            return as_decimal(left), as_decimal(right)
        if isinstance(left, Long) or isinstance(right, Long):
            return Long(left), Long(right)
        return left, right
    if isinstance(left, Quantity) and is_number(right):
        return left, as_quantity(right)
    if isinstance(right, Quantity) and is_number(left):
        return as_quantity(left), right
    if isinstance(left, FPDate) and isinstance(right, FPDateTime):
        return left.to_datetime_value(), right
    if isinstance(left, FPDateTime) and isinstance(right, FPDate):
        return left, right.to_datetime_value()
    return left, right


# ---------------------------------------------------------------------------
# types
# ---------------------------------------------------------------------------


def system_type_name(value: Any) -> Optional[str]:
    if isinstance(value, bool):
        return "Boolean"
    if isinstance(value, Long):
        return "Long"
    if isinstance(value, int):
        return "Integer"
    if isinstance(value, Decimal):
        return "Decimal"
    if isinstance(value, str):
        return "String"
    if isinstance(value, FPDateTime):
        return "DateTime"
    if isinstance(value, FPDate):
        return "Date"
    if isinstance(value, FPTime):
        return "Time"
    if isinstance(value, Quantity):
        return "Quantity"
    return None


def resolve_type(spec: TypeSpecifier, expression: str = "") -> List[Tuple[str, str]]:
    """Candidate ``(namespace, name)`` pairs a type specifier may denote.

    Unqualified names resolve against the FHIR model first, then System. An
    unknown unqualified (or ``FHIR.``-qualified) name is an error; an unknown
    ``System.`` name denotes a type no value has.
    """
    namespace, name = spec.namespace, spec.name
    candidates = []
    if namespace in (None, "FHIR"):
        if (
            name in PRIMITIVE_TYPES
            or lookup_class(name) is not None
            or name
            in (
                "PrimitiveType",
                "SimpleQuantity",
                "MoneyQuantity",
            )
        ):
            candidates.append(("FHIR", name))
    if namespace in (None, "System"):
        if name in SYSTEM_TYPES:
            candidates.append(("System", name))
    if not candidates:
        if namespace == "System":
            return []
        raise EvaluationError("unknown type '%s'" % spec, expression)
    return candidates


def is_type(item: Any, candidates: List[Tuple[str, str]], exact: bool = False) -> bool:
    """Is ``item`` of one of the candidate types (or, unless ``exact``, a subtype)?"""
    if isinstance(item, Node):
        names = item.type_names()
        if exact and item.is_primitive:
            names = names[:1]
        return any(ns == "FHIR" and name in names for ns, name in candidates)
    if isinstance(item, TypeInfo):
        return False
    name = system_type_name(item)
    return any(ns == "System" and (n == name or n == "Any") for ns, n in candidates)


def type_info(item: Any) -> Optional[TypeInfo]:
    if isinstance(item, Node):
        if item.type_name is None:
            return None
        if item.is_primitive:
            parent = PRIMITIVE_PARENTS.get(item.type_name, "PrimitiveType")
            return TypeInfo("SimpleTypeInfo", "FHIR", item.type_name, "FHIR." + parent)
        names = item.type_names()
        base = names[1] if len(names) > 1 else "Base"
        return TypeInfo("ClassInfo", "FHIR", item.type_name, "FHIR." + base)
    name = system_type_name(item)
    if name is None:
        return None
    return TypeInfo("SimpleTypeInfo", "System", name, "System.Any")


__all__ = [
    "MISSING",
    "system",
    "system_collection",
    "to_output",
    "singleton",
    "singleton_value",
    "singleton_boolean",
    "promote",
    "resolve_type",
    "is_type",
    "type_info",
]
