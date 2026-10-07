# _*_ coding: utf-8 _*_
"""Existence, filtering/projection, subsetting and combining functions."""

from functools import cmp_to_key
from typing import Any, List

from ..ast import SortArgument, Unary
from ..operators import comparison
from ..operators.equality import contains_item, distinct
from ..values import (
    MISSING,
    is_type,
    resolve_type,
    singleton,
    singleton_boolean,
    system,
)
from .registry import Call, function

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

#: guard for repeat()/repeatAll() (the spec allows signalling an error)
MAX_REPEAT_ITEMS = 100000


def _booleans(call: Call) -> List[bool]:
    values = []
    for item in call.input:
        value = system(item)
        if value is MISSING:
            continue
        if not isinstance(value, bool):
            raise call.error("input must contain only Boolean values")
        values.append(value)
    return values


# ---------------------------------------------------------------- existence


@function("empty")
def empty(call: Call):
    return [not call.input]


@function("exists", 0, 1)
def exists(call: Call):
    if not call.args:
        return [bool(call.input)]
    return [
        any(call.each_boolean(0, item, i) is True for i, item in enumerate(call.input))
    ]


@function("all", 1)
def all_(call: Call):
    return [
        all(call.each_boolean(0, item, i) is True for i, item in enumerate(call.input))
    ]


@function("allTrue")
def all_true(call: Call):
    return [all(_booleans(call))]


@function("anyTrue")
def any_true(call: Call):
    return [any(_booleans(call))]


@function("allFalse")
def all_false(call: Call):
    return [not any(_booleans(call))]


@function("anyFalse")
def any_false(call: Call):
    return [not all(_booleans(call))]


@function("subsetOf", 1)
def subset_of(call: Call):
    other = call.arg(0)
    return [all(contains_item(other, item) for item in call.input)]


@function("supersetOf", 1)
def superset_of(call: Call):
    other = call.arg(0)
    return [all(contains_item(call.input, item) for item in other)]


@function("count")
def count(call: Call):
    return [len(call.input)]


@function("distinct")
def distinct_(call: Call):
    return distinct(call.input)


@function("isDistinct")
def is_distinct(call: Call):
    return [len(distinct(call.input)) == len(call.input)]


# ------------------------------------------------------ filtering/projection


@function("where", 1)
def where(call: Call):
    return [
        item
        for i, item in enumerate(call.input)
        if call.each_boolean(0, item, i) is True
    ]


@function("select", 1)
def select(call: Call):
    result: List[Any] = []
    for i, item in enumerate(call.input):
        result.extend(call.each(0, item, i))
    return result


def _repeat(call: Call, unique: bool) -> List[Any]:
    result: List[Any] = []
    queue = list(call.input)
    while queue:
        item = queue.pop(0)
        for found in call.each(0, item):
            if unique and contains_item(result, found):
                continue
            result.append(found)
            queue.append(found)
            if len(result) > MAX_REPEAT_ITEMS:
                raise call.error("too many items (possible infinite loop)")
    return result


@function("repeat", 1)
def repeat(call: Call):
    return _repeat(call, unique=True)


@function("repeatAll", 1)
def repeat_all(call: Call):
    return _repeat(call, unique=False)


@function("ofType", 1)
def of_type(call: Call):
    candidates = resolve_type(call.type_arg(0))
    return [item for item in call.input if is_type(item, candidates, exact=True)]


@function("coalesce", 1, 255)
def coalesce(call: Call):
    ctx = call.ctx.derive(this=call.input, index=None)
    for argument in call.args:
        result = call.engine.evaluate(argument, ctx)
        if result:
            return result
    return []


@function("sort", 0, 255)
def sort(call: Call):
    items = list(call.input)
    if not call.args:
        keys = [[system(item)] for item in items]
        directions = [False]
    else:
        expressions, directions = [], []
        for arg in call.args:
            expression = arg.expression if isinstance(arg, SortArgument) else arg
            descending = isinstance(arg, SortArgument) and arg.descending
            # a leading unary minus also requests descending order: sort(-$this)
            if isinstance(expression, Unary) and expression.op == "-":
                expression, descending = expression.operand, not descending
            expressions.append(expression)
            directions.append(descending)
        keys = []
        for item in items:
            ctx = call.ctx.focus(item)
            keys.append(
                [
                    system(singleton(call.engine.evaluate(e, ctx), "sort key"))
                    for e in expressions
                ]
            )

    def compare_rows(a, b):
        for (va, vb), descending in zip(zip(a[0], b[0]), directions):
            if va is MISSING and vb is MISSING:
                continue
            # an empty key sorts first whatever the direction
            if va is MISSING:
                return -1
            if vb is MISSING:
                return 1
            result = comparison.compare(va, vb) or 0
            if result:
                return -result if descending else result
        return 0

    ordered = sorted(zip(keys, items), key=cmp_to_key(compare_rows))
    return [item for _, item in ordered]


# ---------------------------------------------------------------- subsetting


@function("single")
def single(call: Call):
    item = call.input_item()
    return [] if item is MISSING else [item]


@function("first")
def first(call: Call):
    return call.input[:1]


@function("last")
def last(call: Call):
    return call.input[-1:]


@function("tail")
def tail(call: Call):
    return call.input[1:]


@function("skip", 1)
def skip(call: Call):
    num = call.arg_integer(0)
    if num is MISSING or num <= 0:
        return list(call.input)
    return call.input[num:]


@function("take", 1)
def take(call: Call):
    num = call.arg_integer(0)
    if num is MISSING or num <= 0:
        return []
    return call.input[:num]


@function("intersect", 1)
def intersect(call: Call):
    other = call.arg(0)
    return distinct([item for item in call.input if contains_item(other, item)])


@function("exclude", 1)
def exclude(call: Call):
    other = call.arg(0)
    return [item for item in call.input if not contains_item(other, item)]


# ----------------------------------------------------------------- combining


@function("union", 1)
def union(call: Call):
    return distinct(list(call.input) + call.arg(0))


@function("combine", 1, 2)
def combine(call: Call):
    if call.has_arg(1):
        singleton_boolean(call.arg(1), "preserveOrder")
    return list(call.input) + call.arg(0)
