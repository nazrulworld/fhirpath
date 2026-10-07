# _*_ coding: utf-8 _*_
"""Strict parsing of the FHIRPath 3.0.0 grammar into the AST."""

from decimal import Decimal

import pytest

from fhirpath.core import ast
from fhirpath.core.ast import unescape
from fhirpath.core.parser import FHIRPathSyntaxError, parse
from fhirpath.core.types import (
    FPDate,
    FPDateTime,
    FPTime,
    Long,
    Quantity,
    TypeSpecifier,
)

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


@pytest.mark.parametrize(
    "expression",
    [
        "1 + 2 )",
        "2 + 2 /",
        "name..given",
        "@T14:34:28+10:00",
        "@T14:34:28Z",
        "'unterminated",
        "where(",
        "5L L",
        "a.div",
        "1 +",
        "",
    ],
)
def test_syntax_errors_are_raised(expression):
    with pytest.raises(FHIRPathSyntaxError):
        parse(expression)


def test_invalid_temporal_literal_is_a_syntax_error():
    with pytest.raises(FHIRPathSyntaxError):
        parse("@2015-13-01")


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("1", ast.Literal(1)),
        ("1.50", ast.Literal(Decimal("1.50"))),
        ("5L", ast.Literal(Long(5))),
        ("-5", ast.Literal(-5)),
        ("-5L", ast.Literal(Long(-5))),
        ("true", ast.Literal(True)),
        ("{}", ast.Literal(None)),
        ("'a\\'b'", ast.Literal("a'b")),
        ("@2014", ast.Literal(FPDate.parse("2014"))),
        ("@2014T", ast.Literal(FPDateTime.parse("2014"))),
        (
            "@2014-01-25T14:30:14.559+10:00",
            ast.Literal(FPDateTime.parse("2014-01-25T14:30:14.559+10:00")),
        ),
        ("@T14:30", ast.Literal(FPTime.parse("14:30"))),
        ("4.5 'mg'", ast.Literal(Quantity(Decimal("4.5"), "mg"))),
        ("2 years", ast.Literal(Quantity(2, "year"))),
        ("1 week", ast.Literal(Quantity(1, "week"))),
        ("-1.5 'cm'", ast.Literal(Quantity(Decimal("-1.5"), "cm"))),
    ],
)
def test_literals(expression, expected):
    assert parse(expression) == expected


def test_precedence():
    # unary minus binds looser than invocation: -(7.combine(3))
    tree = parse("-7.combine(3)")
    assert isinstance(tree, ast.Unary) and isinstance(tree.operand, ast.Invocation)
    # (-1) + 2
    tree = parse("-x+2")
    assert (
        isinstance(tree, ast.Binary)
        and tree.op == "+"
        and isinstance(tree.left, ast.Unary)
    )
    # a or (b and c)
    tree = parse("a or b and c")
    assert tree.op == "or" and tree.right.op == "and"
    # (x | y) = z
    tree = parse("x | y = z")
    assert tree.op == "=" and tree.left.op == "|"
    # (a is Quantity) and b
    tree = parse("a is Quantity and b")
    assert tree.op == "and" and isinstance(tree.left, ast.TypeOperation)
    # left associative: (1 - 2) - 3
    tree = parse("1 - 2 - 3")
    assert tree.left.op == "-" and tree.right == ast.Literal(3)


def test_invocations_and_identifiers():
    tree = parse("Patient.`name`.where($this.given = 'x')[0]")
    assert isinstance(tree, ast.Indexer)
    where = tree.left
    assert isinstance(where.right, ast.Function) and where.right.name == "where"
    assert where.left.right == ast.Member("name")
    # keywords usable as identifiers
    assert parse("contains.is.as") == ast.Invocation(
        ast.Invocation(ast.Member("contains"), ast.Member("is")), ast.Member("as")
    )
    assert parse("sort.count()").left == ast.Member("sort")
    assert parse("$index") == ast.Index()
    assert parse("$total") == ast.Total()


def test_type_specifiers_and_constants():
    tree = parse("value is FHIR.Quantity")
    assert tree.type_specifier == TypeSpecifier("FHIR", "Quantity")
    assert parse("%`vs-x`") == ast.ExternalConstant("vs-x")
    assert parse("%'legacy'") == ast.ExternalConstant("legacy")


def test_sort_arguments():
    tree = parse("x.sort($this desc, name)")
    args = tree.right.args
    assert args[0].descending and not args[1].descending
    assert args[1].expression == ast.Member("name")


def test_instance_selector():
    tree = parse("Coding { system: 'http://x', code: 'a' }")
    assert isinstance(tree, ast.InstanceSelector)
    assert tree.type_specifier == TypeSpecifier(None, "Coding")
    assert [name for name, _ in tree.elements] == ["system", "code"]
    assert parse("Period {:}").elements == ()


def test_comments_and_whitespace():
    assert parse("2 + 2 // trailing comment") == parse("2+2")
    assert parse("/* block */ 2 +\n\t2") == parse("2+2")


@pytest.mark.parametrize(
    "raw,expected",
    [
        (r"\'", "'"),
        (r"\"", '"'),
        (r"\`", "`"),
        (r"\\", "\\"),
        (r"\/", "/"),
        (r"\t\n\r\f", "\t\n\r\f"),
        (r"é", "é"),
        (r"🔥", "🔥"),
        (r"\p", "p"),
        (r"\3", "3"),
    ],
)
def test_unescape(raw, expected):
    assert unescape(raw) == expected


def test_parse_is_cached():
    assert parse("name.given") is parse("name.given")
