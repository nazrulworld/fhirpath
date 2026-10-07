# _*_ coding: utf-8 _*_
"""Abstract syntax tree for FHIRPath expressions and the ANTLR visitor building it.

The tree is immutable and independent of ANTLR, so compiled expressions can be
cached and evaluated concurrently.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional, Tuple

from .antlr4_grammer.FHIRPathExpressionParser import FHIRPathExpressionParser as P
from .antlr4_grammer.FHIRPathExpressionVisitor import FHIRPathExpressionVisitor
from .evaluation import EvaluationError
from .types import (
    CALENDAR_UNITS,
    FPDate,
    FPDateTime,
    FPTime,
    Long,
    Quantity,
    TypeSpecifier,
)

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


class Node:
    """Base class of all AST nodes."""

    __slots__ = ()


@dataclass(frozen=True)
class Literal(Node):
    """A literal; ``value`` is ``None`` for the empty collection ``{ }``."""

    value: Any


@dataclass(frozen=True)
class ExternalConstant(Node):
    name: str


@dataclass(frozen=True)
class Member(Node):
    name: str


@dataclass(frozen=True)
class SortArgument(Node):
    expression: Node
    descending: bool = False


@dataclass(frozen=True)
class Function(Node):
    name: str
    args: Tuple[Node, ...] = ()


@dataclass(frozen=True)
class This(Node):
    pass


@dataclass(frozen=True)
class Index(Node):
    pass


@dataclass(frozen=True)
class Total(Node):
    pass


@dataclass(frozen=True)
class Invocation(Node):
    """``left . right`` where ``right`` is Member, Function, This, Index or Total."""

    left: Node
    right: Node


@dataclass(frozen=True)
class Indexer(Node):
    left: Node
    index: Node


@dataclass(frozen=True)
class Unary(Node):
    op: str
    operand: Node


@dataclass(frozen=True)
class Binary(Node):
    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class TypeOperation(Node):
    """``left is T`` / ``left as T``."""

    op: str
    left: Node
    type_specifier: TypeSpecifier


@dataclass(frozen=True)
class InstanceSelector(Node):
    type_specifier: TypeSpecifier
    elements: Tuple[Tuple[str, Node], ...]


# ---------------------------------------------------------------------------
# Lexical helpers
# ---------------------------------------------------------------------------

_SIMPLE_ESCAPES = {
    "'": "'",
    '"': '"',
    "`": "`",
    "\\": "\\",
    "/": "/",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


def unescape(text: str) -> str:
    """Process FHIRPath escapes in the body of a string or delimited identifier.

    ``\\uXXXX`` sequences are UTF-16 code units; surrogate pairs are combined.
    Unknown escapes drop the backslash (``'\\p'`` is ``'p'``).
    """
    units = []
    pos = 0
    length = len(text)
    while pos < length:
        char = text[pos]
        if char != "\\" or pos + 1 >= length:
            if char != "\\":
                units.append(char)
            pos += 1
            continue
        nxt = text[pos + 1]
        if nxt in _SIMPLE_ESCAPES:
            units.append(_SIMPLE_ESCAPES[nxt])
            pos += 2
        elif nxt == "u" and _is_hex(text[pos + 2 : pos + 6]):
            units.append(int(text[pos + 2 : pos + 6], 16))
            pos += 6
        else:
            units.append(nxt)
            pos += 2
    # combine surrogate pairs
    out = []
    index = 0
    while index < len(units):
        unit = units[index]
        if isinstance(unit, int):
            if 0xD800 <= unit <= 0xDBFF and index + 1 < len(units):
                low = units[index + 1]
                if isinstance(low, int) and 0xDC00 <= low <= 0xDFFF:
                    out.append(chr(0x10000 + ((unit - 0xD800) << 10) + (low - 0xDC00)))
                    index += 2
                    continue
            if 0xD800 <= unit <= 0xDFFF:
                raise EvaluationError("invalid lone surrogate in string literal", "")
            out.append(chr(unit))
        else:
            out.append(unit)
        index += 1
    return "".join(out)


def _is_hex(text: str) -> bool:
    return len(text) == 4 and all(c in "0123456789abcdefABCDEF" for c in text)


def identifier_text(ctx) -> str:
    text = ctx.getText()
    if text.startswith("`"):
        return unescape(text[1:-1])
    return text


def qualified_type(ctx) -> TypeSpecifier:
    names = [identifier_text(i) for i in ctx.identifier()]
    if len(names) == 1:
        return TypeSpecifier(None, names[0])
    return TypeSpecifier(".".join(names[:-1]), names[-1])


def parse_temporal(text: str, kind):
    value = kind.parse(text)
    if value is None:
        raise EvaluationError(
            "invalid %s literal @%s" % (kind.__name__[2:], text), text
        )
    return value


# ---------------------------------------------------------------------------
# Visitor
# ---------------------------------------------------------------------------


class AstBuilder(FHIRPathExpressionVisitor):
    """Turns an ANTLR parse tree into :mod:`ast` nodes."""

    def visitEntireExpression(self, ctx: P.EntireExpressionContext):
        return self.visit(ctx.expression())

    # -- expressions ---------------------------------------------------------
    def visitTermExpression(self, ctx):
        return self.visit(ctx.term())

    def visitInvocationExpression(self, ctx):
        return Invocation(self.visit(ctx.expression()), self.visit(ctx.invocation()))

    def visitIndexerExpression(self, ctx):
        left, index = ctx.expression()
        return Indexer(self.visit(left), self.visit(index))

    def visitPolarityExpression(self, ctx):
        operand = self.visit(ctx.expression())
        op = ctx.getChild(0).getText()
        # fold signs into numeric literals so that -2147483648 etc. stay exact
        if isinstance(operand, Literal) and op == "-":
            value = operand.value
            if isinstance(value, Long):
                return Literal(Long(-value))
            if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
                return Literal(-value)
            if isinstance(value, Quantity):
                return Literal(Quantity(-value.value, value.unit))
        return Unary(op, operand)

    def _binary(self, ctx):
        left, right = ctx.expression()
        return Binary(ctx.getChild(1).getText(), self.visit(left), self.visit(right))

    visitMultiplicativeExpression = _binary
    visitAdditiveExpression = _binary
    visitUnionExpression = _binary
    visitInequalityExpression = _binary
    visitEqualityExpression = _binary
    visitMembershipExpression = _binary
    visitAndExpression = _binary
    visitOrExpression = _binary
    visitImpliesExpression = _binary

    def visitTypeExpression(self, ctx):
        return TypeOperation(
            ctx.getChild(1).getText(),
            self.visit(ctx.expression()),
            qualified_type(ctx.typeSpecifier().qualifiedIdentifier()),
        )

    # -- terms -----------------------------------------------------------------
    def visitInvocationTerm(self, ctx):
        return self.visit(ctx.invocation())

    def visitLiteralTerm(self, ctx):
        return self.visit(ctx.literal())

    def visitExternalConstantTerm(self, ctx):
        return self.visit(ctx.externalConstant())

    def visitParenthesizedTerm(self, ctx):
        return self.visit(ctx.expression())

    def visitInstanceSelectorTerm(self, ctx):
        selector = ctx.instanceSelector()
        elements = tuple(
            (identifier_text(e.identifier()), self.visit(e.expression()))
            for e in selector.instanceElementSelector()
        )
        return InstanceSelector(
            qualified_type(selector.qualifiedIdentifier()), elements
        )

    def visitExternalConstant(self, ctx):
        if ctx.identifier() is not None:
            return ExternalConstant(identifier_text(ctx.identifier()))
        return ExternalConstant(unescape(ctx.STRING().getText()[1:-1]))

    # -- literals --------------------------------------------------------------
    def visitNullLiteral(self, ctx):
        return Literal(None)

    def visitBooleanLiteral(self, ctx):
        return Literal(ctx.getText() == "true")

    def visitStringLiteral(self, ctx):
        return Literal(unescape(ctx.getText()[1:-1]))

    def visitNumberLiteral(self, ctx):
        text = ctx.getText()
        if ctx.DECIMAL() is not None:
            return Literal(Decimal(text))
        return Literal(int(text))

    def visitLongNumberLiteral(self, ctx):
        return Literal(Long(int(ctx.getText()[:-1])))

    def visitDateLiteral(self, ctx):
        return Literal(parse_temporal(ctx.getText()[1:], FPDate))

    def visitDateTimeLiteral(self, ctx):
        return Literal(parse_temporal(ctx.getText()[1:], FPDateTime))

    def visitTimeLiteral(self, ctx):
        return Literal(parse_temporal(ctx.getText()[2:], FPTime))

    def visitQuantityLiteral(self, ctx):
        quantity = ctx.quantity()
        number = quantity.getChild(0).getText()
        unit = quantity.unit()
        if unit is None:
            unit_text = "1"
        elif unit.STRING() is not None:
            unit_text = unescape(unit.STRING().getText()[1:-1])
        else:
            unit_text = CALENDAR_UNITS[unit.getText()]
        return Literal(Quantity(Decimal(number), unit_text))

    # -- invocations -------------------------------------------------------------
    def visitMemberInvocation(self, ctx):
        return Member(identifier_text(ctx.identifier()))

    def visitFunctionInvocation(self, ctx):
        function = ctx.function()
        if function.identifier() is None:  # the special 'sort' alternative
            args = tuple(
                SortArgument(
                    self.visit(arg.expression()),
                    arg.getChildCount() > 1 and arg.getChild(1).getText() == "desc",
                )
                for arg in function.sortArgument()
            )
            return Function("sort", args)
        params = function.paramList()
        args = tuple(self.visit(e) for e in params.expression()) if params else ()
        return Function(identifier_text(function.identifier()), args)

    def visitThisInvocation(self, ctx):
        return This()

    def visitIndexInvocation(self, ctx):
        return Index()

    def visitTotalInvocation(self, ctx):
        return Total()


def type_specifier_from(node: Node) -> Optional[TypeSpecifier]:
    """Interpret a function argument (``ofType(FHIR.Patient)``) as a type specifier."""
    names = []
    while isinstance(node, Invocation):
        if not isinstance(node.right, Member):
            return None
        names.insert(0, node.right.name)
        node = node.left
    if not isinstance(node, Member):
        return None
    names.insert(0, node.name)
    if len(names) == 1:
        return TypeSpecifier(None, names[0])
    return TypeSpecifier(".".join(names[:-1]), names[-1])


__all__ = [
    "Node",
    "Literal",
    "ExternalConstant",
    "Member",
    "Function",
    "SortArgument",
    "This",
    "Index",
    "Total",
    "Invocation",
    "Indexer",
    "Unary",
    "Binary",
    "TypeOperation",
    "InstanceSelector",
    "AstBuilder",
    "type_specifier_from",
    "unescape",
]
