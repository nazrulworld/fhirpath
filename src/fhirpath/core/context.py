# _*_ coding: utf-8 _*_
"""Evaluation context: ``$this``/``$index``/``$total``, ``%variables`` and host hooks."""

import datetime
import logging
from typing import Any, Callable, Dict, List, Optional

from .types import FPDateTime

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

LOG = logging.getLogger("fhirpath.trace")

#: Resolver hook: (reference string, context node or None) -> resource (model/dict) or None
Resolver = Callable[[str, Any], Any]
#: Trace hook: (name, collection) -> None
Tracer = Callable[[str, List[Any]], None]


class Terminology:
    """Optional terminology service used by ``memberOf``/``subsumes``/``subsumedBy``.

    Methods return ``True``/``False``, or ``None`` when the answer is unknown.
    """

    def member_of(
        self, value: Any, valueset: str
    ) -> Optional[bool]:  # pragma: no cover
        raise NotImplementedError

    def subsumes(
        self, system: str, code_a: str, code_b: str
    ) -> Optional[bool]:  # pragma: no cover
        raise NotImplementedError


def default_tracer(name: str, collection: List[Any]):
    LOG.debug("%s: %r", name, collection)


class Environment:
    """State shared by a whole evaluation (frozen clock, hooks)."""

    __slots__ = ("now", "resolver", "tracer", "terminology")

    def __init__(
        self,
        now: Optional[FPDateTime] = None,
        resolver: Optional[Resolver] = None,
        tracer: Optional[Tracer] = None,
        terminology: Optional[Terminology] = None,
    ):
        if now is None:
            current = datetime.datetime.now().astimezone()
            current = current.replace(microsecond=(current.microsecond // 1000) * 1000)
            now = FPDateTime.from_python(current)
            now.precision = 6  # millisecond precision, even at .000
        self.now = now
        self.resolver = resolver
        self.tracer = tracer or default_tracer
        self.terminology = terminology


class EvalContext:
    """Immutable evaluation scope; use :meth:`derive` to change it."""

    __slots__ = ("this", "index", "total", "variables", "env", "defined")

    def __init__(
        self,
        this: List[Any],
        variables: Dict[str, List[Any]],
        env: Environment,
        index: Optional[int] = None,
        total: Optional[List[Any]] = None,
        defined: frozenset = frozenset(),
    ):
        self.this = this
        self.variables = variables
        self.env = env
        self.index = index
        self.total = total
        self.defined = defined

    def derive(self, **changes) -> "EvalContext":
        values = {name: getattr(self, name) for name in self.__slots__}
        values.update(changes)
        return EvalContext(**values)

    def focus(self, item: Any, index: Optional[int] = None) -> "EvalContext":
        """Scope for one item of a scoped function (``$this``/``$index``)."""
        return self.derive(this=[item], index=index)

    def define(self, name: str, value: List[Any]) -> "EvalContext":
        variables = dict(self.variables)
        variables[name] = value
        return self.derive(variables=variables, defined=self.defined | {name})


__all__ = ["EvalContext", "Environment", "Terminology", "Resolver", "Tracer"]
