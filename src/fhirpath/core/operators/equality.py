# _*_ coding: utf-8 _*_
"""``=`` / ``!=`` (equality) and ``~`` / ``!~`` (equivalence)."""

import unicodedata
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..model import Node
from ..types import (
    FPDate,
    FPDateTime,
    FPTime,
    Quantity,
    TypeInfo,
    round_half_away,
    significant_places,
)
from ..values import MISSING, is_number, promote, system
from . import quantity as quantity_ops
from . import temporal

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

_TEMPORAL = (FPDate, FPDateTime, FPTime)


def decimal_equivalent(a: Decimal, b: Decimal) -> bool:
    places = min(significant_places(a), significant_places(b))
    return round_half_away(a, places) == round_half_away(b, places)


def _normalize_string(text: str) -> str:
    return "".join(
        " " if c.isspace() else c for c in unicodedata.normalize("NFC", text)
    ).lower()


# ---------------------------------------------------------------------------
# single items
# ---------------------------------------------------------------------------


def equals(a: Any, b: Any) -> Optional[bool]:
    """FHIRPath ``=`` on two single items: True/False, or None (unknown)."""
    a, b = system(a), system(b)
    if a is MISSING or b is MISSING:
        return None
    if isinstance(a, Node) or isinstance(b, Node):
        if isinstance(a, Node) and isinstance(b, Node):
            return _complex_equals(a, b, equivalence=False)
        return False
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    a, b = promote(a, b)
    if is_number(a) and is_number(b):
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if isinstance(a, _TEMPORAL) and isinstance(b, _TEMPORAL):
        return temporal.equals(a, b)
    if isinstance(a, Quantity) and isinstance(b, Quantity):
        return quantity_ops.equals(a, b)
    if isinstance(a, TypeInfo) and isinstance(b, TypeInfo):
        return a == b
    return False


def equivalent(a: Any, b: Any) -> bool:
    """FHIRPath ``~`` on two single items."""
    a, b = system(a), system(b)
    if a is MISSING or b is MISSING:
        return a is MISSING and b is MISSING
    if isinstance(a, Node) or isinstance(b, Node):
        if isinstance(a, Node) and isinstance(b, Node):
            return bool(_complex_equals(a, b, equivalence=True))
        return False
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    a, b = promote(a, b)
    if is_number(a) and is_number(b):
        if isinstance(a, Decimal) or isinstance(b, Decimal):
            return decimal_equivalent(Decimal(a), Decimal(b))
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return _normalize_string(a) == _normalize_string(b)
    if isinstance(a, _TEMPORAL) and isinstance(b, _TEMPORAL):
        return temporal.equivalent(a, b)
    if isinstance(a, Quantity) and isinstance(b, Quantity):
        return quantity_ops.equivalent(a, b)
    if isinstance(a, TypeInfo) and isinstance(b, TypeInfo):
        return a == b
    return False


# ---------------------------------------------------------------------------
# complex types
# ---------------------------------------------------------------------------


def _grouped(node: Node, drop_id: bool) -> Dict[str, List[Node]]:
    groups: Dict[str, List[Node]] = {}
    for child in node.children():
        if drop_id and child.name == "id":
            continue
        if child.is_primitive and child.value is None:
            continue
        groups.setdefault(child.name, []).append(child)
    return groups


def _complex_equals(a: Node, b: Node, equivalence: bool) -> Optional[bool]:
    if a.is_primitive or b.is_primitive:
        return False
    if equivalence:
        types = {a.type_name, b.type_name}
        if types == {"Coding"}:
            return equivalent_collections(
                a.child("system"), b.child("system")
            ) and equivalent_collections(a.child("code"), b.child("code"))
        if types == {"CodeableConcept"}:
            codings_a, codings_b = a.child("coding"), b.child("coding")
            return any(equivalent(x, y) for x in codings_a for y in codings_b)
    groups_a, groups_b = _grouped(a, equivalence), _grouped(b, equivalence)
    if set(groups_a) != set(groups_b):
        return False
    result: Optional[bool] = True
    for name, items in groups_a.items():
        if equivalence:
            if not equivalent_collections(items, groups_b[name]):
                return False
        else:
            outcome = equal_collections(items, groups_b[name])
            if outcome is False:
                return False
            if outcome is None:
                result = None
    return result


# ---------------------------------------------------------------------------
# collections
# ---------------------------------------------------------------------------


def equal_collections(left: List[Any], right: List[Any]) -> Optional[bool]:
    if not left or not right:
        return None
    if len(left) != len(right):
        return False
    result: Optional[bool] = True
    for a, b in zip(left, right):
        outcome = equals(a, b)
        if outcome is False:
            return False
        if outcome is None:
            result = None
    return result


def equivalent_collections(left: List[Any], right: List[Any]) -> bool:
    if len(left) != len(right):
        return False
    remaining = list(right)
    for item in left:
        for index, candidate in enumerate(remaining):
            if equivalent(item, candidate):
                del remaining[index]
                break
        else:
            return False
    return True


def contains_item(collection: List[Any], item: Any) -> bool:
    """Membership by ``=`` (``true`` only)."""
    return any(equals(item, candidate) is True for candidate in collection)


def distinct(collection: List[Any]) -> List[Any]:
    result: List[Any] = []
    for item in collection:
        if not contains_item(result, item):
            result.append(item)
    return result


__all__ = [
    "equals",
    "equivalent",
    "equal_collections",
    "equivalent_collections",
    "contains_item",
    "distinct",
    "decimal_equivalent",
]
