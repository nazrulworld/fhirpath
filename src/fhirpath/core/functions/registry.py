# _*_ coding: utf-8 _*_
"""Function registry and the :class:`Call` object handed to implementations."""

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from ..ast import Node as AstNode
from ..ast import type_specifier_from
from ..evaluation import EvaluationError
from ..types import TypeSpecifier
from ..values import MISSING, singleton, singleton_boolean, system

if TYPE_CHECKING:  # pragma: no cover
    from ..context import EvalContext
    from ..engine import Engine

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


class FunctionSpec:
    __slots__ = ("name", "impl", "min_args", "max_args")

    def __init__(self, name: str, impl: Callable, min_args: int, max_args: int):
        self.name = name
        self.impl = impl
        self.min_args = min_args
        self.max_args = max_args


FUNCTIONS: Dict[str, FunctionSpec] = {}


def function(name: str, min_args: int = 0, max_args: Optional[int] = None):
    """Register ``impl(call) -> list`` (or :class:`Chain`) as FHIRPath function ``name``."""

    def decorator(impl):
        FUNCTIONS[name] = FunctionSpec(
            name, impl, min_args, min_args if max_args is None else max_args
        )
        return impl

    return decorator


class Chain:
    """Return value of functions that change the context for the rest of the chain."""

    __slots__ = ("result", "ctx")

    def __init__(self, result: List[Any], ctx: "EvalContext"):
        self.result = result
        self.ctx = ctx


class Call:
    """One function invocation: input collection, (lazy) arguments and context."""

    __slots__ = ("engine", "ctx", "input", "args", "name", "_cache")

    def __init__(
        self,
        engine: "Engine",
        ctx: "EvalContext",
        input_: List[Any],
        args: Tuple[AstNode, ...],
        name: str,
    ):
        self.engine = engine
        self.ctx = ctx
        self.input = input_
        self.args = args
        self.name = name
        self._cache: Dict[int, List[Any]] = {}

    # -- errors ----------------------------------------------------------------
    def error(self, message: str) -> EvaluationError:
        return EvaluationError("%s(): %s" % (self.name, message), self.name)

    # -- input -----------------------------------------------------------------
    def input_item(self) -> Any:
        """Single input item (MISSING when empty); error for more than one."""
        return singleton(self.input, "input of %s()" % self.name)

    def input_value(self) -> Any:
        return system(self.input_item())

    def input_string(self) -> Any:
        value = self.input_value()
        if value is MISSING:
            return MISSING
        if not isinstance(value, str):
            raise self.error("input must be a String, got %s" % type(value).__name__)
        return value

    # -- arguments -------------------------------------------------------------
    @property
    def argc(self) -> int:
        return len(self.args)

    def has_arg(self, index: int) -> bool:
        return index < len(self.args)

    def arg(self, index: int) -> List[Any]:
        """Argument evaluated once in the calling context (non-lambda arguments)."""
        if index not in self._cache:
            self._cache[index] = self.engine.evaluate(self.args[index], self.ctx)
        return self._cache[index]

    def arg_item(self, index: int) -> Any:
        return singleton(
            self.arg(index), "argument %d of %s()" % (index + 1, self.name)
        )

    def arg_value(self, index: int) -> Any:
        """Single System value of an argument; MISSING when empty or absent."""
        if not self.has_arg(index):
            return MISSING
        return system(self.arg_item(index))

    def arg_typed(self, index: int, types, label: str) -> Any:
        value = self.arg_value(index)
        if value is MISSING:
            return MISSING
        if isinstance(value, bool) and bool not in types:
            raise self.error("argument %d must be %s" % (index + 1, label))
        if not isinstance(value, types):
            raise self.error("argument %d must be %s" % (index + 1, label))
        return value

    def arg_string(self, index: int) -> Any:
        return self.arg_typed(index, (str,), "a String")

    def arg_integer(self, index: int) -> Any:
        value = self.arg_value(index)
        if value is MISSING:
            return MISSING
        if isinstance(value, bool) or not isinstance(value, int):
            raise self.error("argument %d must be an Integer" % (index + 1))
        return int(value)

    def arg_boolean(self, index: int) -> Any:
        if not self.has_arg(index):
            return MISSING
        return singleton_boolean(
            self.arg(index), "argument %d of %s()" % (index + 1, self.name)
        )

    def type_arg(self, index: int) -> TypeSpecifier:
        spec = type_specifier_from(self.args[index])
        if spec is None:
            raise self.error("argument must be a type specifier")
        return spec

    # -- lambdas -----------------------------------------------------------------
    def each(self, index: int, item: Any, position: Optional[int] = None) -> List[Any]:
        """Evaluate argument ``index`` with ``$this`` = item (and ``$index``)."""
        return self.engine.evaluate(self.args[index], self.ctx.focus(item, position))

    def each_boolean(
        self, index: int, item: Any, position: Optional[int] = None
    ) -> Any:
        return singleton_boolean(
            self.each(index, item, position), "criteria of %s()" % self.name
        )


__all__ = ["FUNCTIONS", "FunctionSpec", "function", "Call", "Chain"]
