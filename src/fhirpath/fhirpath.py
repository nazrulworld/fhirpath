# -*- coding: utf-8 -*-
"""Fluent Python API over the FHIRPath engine (:mod:`fhirpath.core`).

>>> fp = FHIRPath(patient)
>>> fp.Patient.name.where("use = 'official'").given.first().to_list()
['Peter']
>>> fp.name.given.count().to_list()
[5]
>>> fp.birthDate.toString().startsWith("1974").to_list()
[True]

* Attribute access navigates elements (``fp.name.given``); use ``fp["class"]``
  for element names that are Python keywords or clash with this class' API.
* Calling an attribute invokes the FHIRPath function of that name on the
  collection (``fp.name.count()``); ``is_``/``as_``/``not_`` stand for the
  keyword-named functions ``is``/``as``/``not``.
* Arguments of lambda-like functions (``where``, ``select``, ``exists``,
  ``all``, ``repeat``, ``sort``, ``iif``, …) and type arguments (``ofType``,
  ``is``, ``as``) are FHIRPath expression strings, evaluated per item.
  Any other argument is a value: Python values become FHIRPath literals, a
  :class:`FHIRPath` passes its collection, and :class:`Expr` marks an
  expression explicitly (``fp.name.given.combine(Expr("name.family"))``).
* Every step returns a new, immutable :class:`FHIRPath`; results come out with
  :meth:`FHIRPath.to_list` (plain values, as :func:`fhirpath.core.evaluate`
  returns them), iteration, ``len()`` or ``bool()``.
"""

import datetime
from decimal import Decimal
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .core import ast
from .core.context import Environment, EvalContext
from .core.element import _ENGINE
from .core.functions import FUNCTIONS
from .core.parser import parse
from .core.types import FPDate, FPDateTime, FPTime, Long, Quantity
from .core.values import to_output

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

__all__ = ["FHIRPath", "Expr"]

#: function name -> argument positions given as FHIRPath expression strings
#: (``None`` = every argument)
_EXPRESSION_ARGS: Dict[str, Optional[Tuple[int, ...]]] = {
    "where": None,
    "select": None,
    "exists": None,
    "all": None,
    "repeat": None,
    "repeatAll": None,
    "sort": None,
    "iif": None,
    "coalesce": None,
    "aggregate": (0,),
    "trace": (1,),
    "defineVariable": (1,),
    "ofType": None,
    "is": None,
    "as": None,
}
_KEYWORD_FUNCTIONS = {"is_": "is", "as_": "as", "not_": "not"}


class Expr:
    """Marks a string argument as a FHIRPath expression rather than a String value."""

    __slots__ = ("text",)

    def __init__(self, text: str):
        self.text = text

    def __repr__(self):
        return "Expr(%r)" % self.text


class FHIRPath:
    """An immutable FHIRPath collection bound to a resource and evaluation context."""

    __slots__ = ("_items", "_ctx", "_parent", "_name", "_root")

    def __init__(
        self,
        resource: Any = None,
        variables: Optional[Dict[str, Any]] = None,
        *,
        resolver=None,
        terminology=None,
        tracer=None,
        now=None,
    ):
        root = _ENGINE.root_collection(resource)
        env = Environment(
            now=now, resolver=resolver, tracer=tracer, terminology=terminology
        )
        ctx = EvalContext(
            this=root, variables=_ENGINE.initial_variables(root, variables), env=env
        )
        self._init(root, ctx, None, None, True)

    # ------------------------------------------------------------ internals
    def _init(self, items, ctx, parent, name, root):
        object.__setattr__(self, "_items", items)
        object.__setattr__(self, "_ctx", ctx)
        object.__setattr__(self, "_parent", parent)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_root", root)

    @classmethod
    def _derive(cls, items, ctx, parent=None, name=None) -> "FHIRPath":
        instance = cls.__new__(cls)
        instance._init(items, ctx, parent, name, False)
        return instance

    def _collection(self) -> List[Any]:
        if self._items is None:  # pending navigation, computed on first use
            parent = self._parent
            items = _ENGINE.navigate(
                parent._collection(), self._name, term=parent._root
            )
            object.__setattr__(self, "_items", items)
        return self._items

    def __setattr__(self, key, value):
        raise TypeError("FHIRPath objects are immutable")

    # ----------------------------------------------------------- navigation
    def __getattr__(self, name: str) -> "FHIRPath":
        if name.startswith("_") and name not in _KEYWORD_FUNCTIONS:
            raise AttributeError(name)
        # navigation is lazy: calling the result invokes a function instead
        return self._derive(None, self._ctx, self, name)

    def __getitem__(self, key):
        if isinstance(key, str):
            return self.__getattr__(key)
        items = self._collection()
        if isinstance(key, slice):
            return self._derive(items[key], self._ctx)
        if isinstance(key, bool) or not isinstance(key, int):
            raise TypeError("index must be an int, slice or element name")
        # FHIRPath indexer semantics: out of range -> empty
        return self._derive(items[key : key + 1] if key >= 0 else [], self._ctx)

    # ------------------------------------------------------------ functions
    def __call__(self, *args: Any) -> "FHIRPath":
        if self._parent is None:
            raise TypeError(
                "only functions can be called, e.g. FHIRPath(r).name.count()"
            )
        name = _KEYWORD_FUNCTIONS.get(self._name, self._name)
        if name not in FUNCTIONS:
            raise AttributeError("unknown FHIRPath function %r" % name)
        ctx = self._parent._ctx
        variables: Dict[str, Any] = {}
        if name == "sort":
            # keys carry 'asc'/'desc', which only the sort() grammar rule accepts
            function = parse("sort(%s)" % ", ".join(_sort_text(a) for a in args))
        else:
            positions = _EXPRESSION_ARGS.get(name, ())
            function = ast.Function(
                name,
                tuple(
                    self._argument(
                        arg, positions is None or i in positions, i, variables
                    )
                    for i, arg in enumerate(args)
                ),
            )
        if variables:
            ctx = ctx.derive(variables={**ctx.variables, **variables})
        items, ctx = _ENGINE.invoke(
            function, self._parent._collection(), ctx, term=self._parent._root
        )
        if variables:
            ctx = ctx.derive(
                variables={k: v for k, v in ctx.variables.items() if k not in variables}
            )
        return self._derive(items, ctx)

    @staticmethod
    def _argument(
        arg: Any, as_expression: bool, position: int, variables: Dict[str, Any]
    ) -> ast.Node:
        if isinstance(arg, Expr):
            return parse(arg.text)
        if isinstance(arg, str) and as_expression:
            return parse(arg)
        literal = _literal(arg)
        if literal is not None:
            return literal
        # anything else (a FHIRPath, a list, a resource) is passed as a hidden variable
        name = " arg%d" % position
        if isinstance(arg, FHIRPath):
            variables[name] = list(arg._collection())
        else:
            values = arg if isinstance(arg, (list, tuple)) else [arg]
            variables[name] = _ENGINE.initial_variables([], {name: list(values)})[name]
        return ast.ExternalConstant(name)

    def evaluate(self, expression: str) -> "FHIRPath":
        """Evaluate an expression with this collection as its input (``$this``)."""
        ctx = self._ctx.derive(this=list(self._collection()), index=None)
        items, ctx = _ENGINE.chain(parse(expression), ctx)
        return self._derive(items, ctx)

    # --------------------------------------------------------------- output
    def to_list(self) -> List[Any]:
        """The collection as plain Python values (see :func:`fhirpath.core.evaluate`)."""
        return [
            value for value in map(to_output, self._collection()) if value is not None
        ]

    def to_nodes(self) -> List[Any]:
        """The raw collection items (:class:`fhirpath.core.model.Node` for FHIR data)."""
        return list(self._collection())

    def __iter__(self) -> Iterator[Any]:
        return iter(self.to_list())

    def __len__(self) -> int:
        return len(self._collection())

    def __bool__(self) -> bool:
        """Predicate semantics: a single Boolean is itself, otherwise non-empty."""
        values = self.to_list()
        if len(values) == 1 and isinstance(values[0], bool):
            return values[0]
        return len(values) > 0

    def __repr__(self) -> str:
        return "FHIRPath(%r)" % (self.to_list(),)

    def __dir__(self):
        return sorted(
            set(object.__dir__(self)) | set(FUNCTIONS) | set(_KEYWORD_FUNCTIONS)
        )


def _literal(value: Any) -> Optional[ast.Literal]:
    if value is None:
        return ast.Literal(None)
    if isinstance(
        value, (bool, str, Long, Decimal, FPDate, FPDateTime, FPTime, Quantity)
    ):
        return ast.Literal(value)
    if isinstance(value, int):
        return ast.Literal(value)
    if isinstance(value, float):
        return ast.Literal(Decimal(repr(value)))
    if isinstance(value, datetime.datetime):
        return ast.Literal(FPDateTime.from_python(value))
    if isinstance(value, datetime.date):
        return ast.Literal(FPDate.from_python(value))
    if isinstance(value, datetime.time):
        return ast.Literal(FPTime.from_python(value))
    return None


def _sort_text(arg: Any) -> str:
    if isinstance(arg, Expr):
        return arg.text
    if isinstance(arg, str):
        return arg
    raise TypeError("sort() keys must be expression strings, e.g. 'family desc'")
