# _*_ coding: utf-8 _*_
"""Strict FHIRPath parser: source text -> :mod:`fhirpath.core.ast` tree."""

from functools import lru_cache

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from .antlr4_grammer.FHIRPathExpressionLexer import FHIRPathExpressionLexer
from .antlr4_grammer.FHIRPathExpressionParser import FHIRPathExpressionParser
from .ast import AstBuilder, Node
from .evaluation import EvaluationError

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


class FHIRPathSyntaxError(EvaluationError):
    """The expression is not valid FHIRPath syntax."""

    __slots__ = ("line", "column")

    def __init__(self, msg: str, expression: str, line: int = 0, column: int = 0):
        EvaluationError.__init__(self, msg, expression)
        object.__setattr__(self, "line", line)
        object.__setattr__(self, "column", column)


class _RaisingErrorListener(ErrorListener):
    def __init__(self, expression: str):
        self.expression = expression

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        raise FHIRPathSyntaxError(
            "syntax error at %d:%d: %s" % (line, column, msg),
            self.expression,
            line,
            column,
        )


@lru_cache(maxsize=1024)
def parse(expression: str) -> Node:
    """Parse ``expression``; raises :class:`FHIRPathSyntaxError` on any error."""
    listener = _RaisingErrorListener(expression)

    lexer = FHIRPathExpressionLexer(InputStream(expression))
    lexer.removeErrorListeners()
    lexer.addErrorListener(listener)

    parser = FHIRPathExpressionParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(listener)

    tree = parser.entireExpression()
    try:
        return AstBuilder().visit(tree)
    except EvaluationError as exc:
        raise FHIRPathSyntaxError(exc.msg, expression) from exc


__all__ = ["parse", "FHIRPathSyntaxError"]
