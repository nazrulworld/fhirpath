# _*_ coding: utf-8 _*_
"""String manipulation functions."""

import base64
import binascii
import html
import json
import re
from typing import Any, List

from ..values import MISSING, system
from .registry import Call, function

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

_WHITESPACE = " \t\n\r"


def _string_call(call: Call, *arg_names: str):
    """-> (input string, [string args]) or None when anything is empty."""
    value = call.input_string()
    if value is MISSING:
        return None
    args = []
    for index in range(len(arg_names)):
        arg = call.arg_string(index)
        if arg is MISSING:
            return None
        args.append(arg)
    return value, args


@function("indexOf", 1)
def index_of(call: Call):
    found = _string_call(call, "substring")
    if found is None:
        return []
    value, (substring,) = found
    return [value.find(substring)]


@function("lastIndexOf", 1)
def last_index_of(call: Call):
    found = _string_call(call, "substring")
    if found is None:
        return []
    value, (substring,) = found
    return [value.rfind(substring)]


@function("substring", 1, 2)
def substring(call: Call):
    value = call.input_string()
    start = call.arg_integer(0)
    if value is MISSING or start is MISSING:
        return []
    if start < 0 or start >= len(value):
        return []
    length = call.arg_integer(1) if call.has_arg(1) else MISSING
    if length is MISSING:
        return [value[start:]]
    if length <= 0:
        return [""]
    return [value[start : start + length]]


@function("startsWith", 1)
def starts_with(call: Call):
    found = _string_call(call, "prefix")
    return [] if found is None else [found[0].startswith(found[1][0])]


@function("endsWith", 1)
def ends_with(call: Call):
    found = _string_call(call, "suffix")
    return [] if found is None else [found[0].endswith(found[1][0])]


@function("contains", 1)
def contains(call: Call):
    found = _string_call(call, "substring")
    return [] if found is None else [found[1][0] in found[0]]


@function("upper")
def upper(call: Call):
    value = call.input_string()
    return [] if value is MISSING else [value.upper()]


@function("lower")
def lower(call: Call):
    value = call.input_string()
    return [] if value is MISSING else [value.lower()]


@function("replace", 2)
def replace(call: Call):
    found = _string_call(call, "pattern", "substitution")
    if found is None:
        return []
    value, (pattern, substitution) = found
    return [value.replace(pattern, substitution)]


def _regex_flags(call: Call, index: int) -> int:
    # FHIRPath regexes run in single-line mode: '.' also matches newlines
    flags = re.DOTALL
    if not call.has_arg(index):
        return flags
    flags_text = call.arg_string(index)
    if flags_text is MISSING:
        return flags
    for flag in flags_text:
        if flag == "i":
            flags |= re.IGNORECASE
        elif flag == "m":
            flags |= re.MULTILINE
        else:
            raise call.error("invalid regex flag '%s'" % flag)
    return flags


def compile_regex(call: Call, pattern: str, flags: int):
    pattern = re.sub(r"\(\?<([A-Za-z_][A-Za-z0-9_]*)>", r"(?P<\1>", pattern)
    pattern = re.sub(r"\\k<([A-Za-z_][A-Za-z0-9_]*)>", r"(?P=\1)", pattern)
    try:
        return re.compile(pattern, flags)
    except re.error as exc:
        raise call.error("invalid regular expression: %s" % exc)


@function("matches", 1, 2)
def matches(call: Call):
    found = _string_call(call, "regex")
    if found is None:
        return []
    value, (pattern,) = found
    flags = _regex_flags(call, 1)
    if pattern == "":
        return []
    return [compile_regex(call, pattern, flags).search(value) is not None]


@function("matchesFull", 1, 2)
def matches_full(call: Call):
    found = _string_call(call, "regex")
    if found is None:
        return []
    value, (pattern,) = found
    flags = _regex_flags(call, 1)
    if pattern == "":
        return []
    return [compile_regex(call, pattern, flags).fullmatch(value) is not None]


def _substitution(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", r"\\g<\1>", text)
    return re.sub(r"\$(\d+)", r"\\g<\1>", text)


@function("replaceMatches", 2, 3)
def replace_matches(call: Call):
    found = _string_call(call, "regex", "substitution")
    if found is None:
        return []
    value, (pattern, substitution) = found
    flags = _regex_flags(call, 2)
    if pattern == "":
        return [value]
    regex = compile_regex(call, pattern, flags)
    try:
        return [regex.sub(_substitution(substitution), value)]
    except (re.error, IndexError) as exc:
        raise call.error("invalid substitution: %s" % exc)


@function("length")
def length(call: Call):
    value = call.input_string()
    return [] if value is MISSING else [len(value)]


@function("toChars")
def to_chars(call: Call):
    value = call.input_string()
    return [] if value is MISSING else list(value)


@function("trim")
def trim(call: Call):
    value = call.input_string()
    return [] if value is MISSING else [value.strip(_WHITESPACE)]


@function("split", 1)
def split(call: Call):
    found = _string_call(call, "separator")
    if found is None:
        return []
    value, (separator,) = found
    if separator == "":
        return list(value)
    return value.split(separator)


@function("join", 0, 1)
def join(call: Call):
    separator = call.arg_string(0) if call.has_arg(0) else ""
    if separator is MISSING:
        separator = ""
    parts: List[str] = []
    for item in call.input:
        value = system(item)
        if value is MISSING:
            continue
        if not isinstance(value, str):
            raise call.error("input must contain only Strings")
        parts.append(value)
    if not call.input:
        return []
    return [separator.join(parts)]


@function("encode", 1)
def encode(call: Call):
    found = _string_call(call, "format")
    if found is None:
        return []
    value, (fmt,) = found
    data = value.encode("utf-8")
    if fmt == "hex":
        return [binascii.hexlify(data).decode("ascii")]
    if fmt == "base64":
        return [base64.b64encode(data).decode("ascii")]
    if fmt == "urlbase64":
        return [base64.urlsafe_b64encode(data).decode("ascii")]
    if fmt == "ascii":
        return ["".join(c if ord(c) < 128 else "?" for c in value)]
    return []


@function("decode", 1)
def decode(call: Call):
    found = _string_call(call, "format")
    if found is None:
        return []
    value, (fmt,) = found
    try:
        if fmt == "hex":
            data = binascii.unhexlify(value)
        elif fmt == "base64":
            data = base64.b64decode(value, validate=True)
        elif fmt == "urlbase64":
            data = base64.urlsafe_b64decode(value)
        else:
            return []
        return [data.decode("utf-8")]
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return []


@function("escape", 1)
def escape(call: Call):
    found = _string_call(call, "target")
    if found is None:
        return []
    value, (target,) = found
    if target == "html":
        return [html.escape(value, quote=True).replace("&#x27;", "&#39;")]
    if target == "json":
        return [json.dumps(value, ensure_ascii=False)[1:-1]]
    return []


@function("unescape", 1)
def unescape(call: Call):
    found = _string_call(call, "target")
    if found is None:
        return []
    value, (target,) = found
    if target == "html":
        return [html.unescape(value)]
    if target == "json":
        return [_JSON_ESCAPE.sub(_json_unescape, value)]
    return []


_JSON_ESCAPE = re.compile(r"\\(u[0-9a-fA-F]{4}|[\"\\/bfnrt])")
_JSON_SIMPLE = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


def _json_unescape(match) -> str:
    code = match.group(1)
    if code.startswith("u"):
        return chr(int(code[1:], 16))
    return _JSON_SIMPLE[code]


__all__: List[Any] = []
