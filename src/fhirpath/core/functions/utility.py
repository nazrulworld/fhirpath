# _*_ coding: utf-8 _*_
"""Utility, boolean, type, tree navigation and aggregate functions."""

from decimal import Decimal
from typing import Any, List

from ..model import Node
from ..operators import arithmetic, comparison
from ..types import FPDate, FPDateTime, FPTime, Quantity
from ..values import (
    MISSING,
    is_number,
    is_type,
    resolve_type,
    singleton_boolean,
    system_collection,
    to_output,
    type_info,
)
from .registry import Call, Chain, function

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


# ------------------------------------------------------------------- boolean


@function("not")
def not_(call: Call):
    value = singleton_boolean(call.input, "input of not()")
    return [] if value is MISSING else [not value]


# ------------------------------------------------------------------- utility


@function("trace", 1, 2)
def trace(call: Call):
    name = call.arg_string(0)
    if call.has_arg(1):
        logged: List[Any] = []
        for i, item in enumerate(call.input):
            logged.extend(call.each(1, item, i))
    else:
        logged = list(call.input)
    outputs = [value for value in map(to_output, logged) if value is not None]
    call.ctx.env.tracer("" if name is MISSING else name, outputs)
    return list(call.input)


@function("now")
def now(call: Call):
    return [call.ctx.env.now]


@function("today")
def today(call: Call):
    return [call.ctx.env.now.to_date()]


@function("timeOfDay")
def time_of_day(call: Call):
    return [call.ctx.env.now.to_time()]


@function("defineVariable", 1, 2)
def define_variable(call: Call):
    name = call.arg_string(0)
    if name is MISSING:
        raise call.error("variable name must be a String")
    if name in call.ctx.variables:
        raise call.error("variable %%%s is already defined" % name)
    if call.has_arg(1):
        value = call.engine.evaluate(
            call.args[1], call.ctx.derive(this=call.input, index=None)
        )
    else:
        value = list(call.input)
    return Chain(list(call.input), call.ctx.define(name, value))


# --------------------------------------------------------------------- types


@function("is", 1)
def is_(call: Call):
    candidates = resolve_type(call.type_arg(0))
    item = call.input_item()
    if item is MISSING:
        return []
    return [is_type(item, candidates)]


@function("as", 1)
def as_(call: Call):
    candidates = resolve_type(call.type_arg(0))
    item = call.input_item()
    if item is MISSING:
        return []
    return [item] if is_type(item, candidates, exact=True) else []


@function("type")
def type_(call: Call):
    result = []
    for item in call.input:
        info = type_info(item)
        if info is not None:
            result.append(info)
    return result


# ------------------------------------------------------------ tree navigation


@function("children")
def children(call: Call):
    result: List[Any] = []
    for item in call.input:
        if isinstance(item, Node):
            result.extend(item.children())
    return result


@function("descendants")
def descendants(call: Call):
    result: List[Any] = []
    queue = [item for item in call.input if isinstance(item, Node)]
    while queue:
        node = queue.pop(0)
        for child in node.children():
            result.append(child)
            queue.append(child)
    return result


# ---------------------------------------------------------------- aggregates


@function("aggregate", 1, 2)
def aggregate(call: Call):
    total = call.arg(1) if call.has_arg(1) else []
    for index, item in enumerate(call.input):
        ctx = call.ctx.derive(this=[item], index=index, total=total)
        total = call.engine.evaluate(call.args[0], ctx)
    return total


def _homogeneous(call: Call, allowed) -> List[Any]:
    values = system_collection(call.input)
    kind = None
    for value in values:
        if isinstance(value, bool) or not isinstance(value, allowed):
            raise call.error("unsupported item type %s" % type(value).__name__)
        current = "number" if is_number(value) else type(value)
        if kind is not None and current != kind:
            raise call.error("items must all have the same type")
        kind = current
    return values


@function("sum")
def sum_(call: Call):
    values = _homogeneous(call, (int, Decimal, Quantity))
    if not values:
        return []
    total = values[0]
    for value in values[1:]:
        total = arithmetic.apply("+", total, value)
        if total is None:
            return []
    return [total]


def _extreme(call: Call, sign: int):
    values = _homogeneous(
        call, (int, Decimal, Quantity, FPDate, FPDateTime, FPTime, str)
    )
    if not values:
        return []
    best = values[0]
    for value in values[1:]:
        outcome = comparison.compare(value, best)
        if outcome is None:
            return []
        if outcome * sign > 0:
            best = value
    return [best]


@function("min")
def min_(call: Call):
    return _extreme(call, -1)


@function("max")
def max_(call: Call):
    return _extreme(call, 1)


@function("avg")
def avg(call: Call):
    values = _homogeneous(call, (int, Decimal, Quantity))
    if not values:
        return []
    total = values[0]
    for value in values[1:]:
        total = arithmetic.apply("+", total, value)
        if total is None:
            return []
    if isinstance(total, Quantity):
        return [Quantity(total.value / len(values), total.unit)]
    return [Decimal(total) / Decimal(len(values))]


__all__: List[Any] = []
