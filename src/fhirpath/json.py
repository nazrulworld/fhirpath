import typing
from decimal import Decimal

from pydantic import BaseModel
from pydantic_core import to_jsonable_python

try:
    import orjson as json_mod
except ImportError:
    try:
        import simplejson as json_mod  # type:ignore
    except ImportError:
        import json as json_mod  # type:ignore

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def json_default(value: typing.Any) -> typing.Any:
    """``default`` hook for JSON encoders (replaces pydantic 1 ``pydantic_encoder``).

    FHIR models are dumped as FHIR JSON (aliases, no empty elements), decimals as
    JSON numbers, anything else pydantic knows (dates, UUIDs, enums, bytes, ...) via
    ``pydantic_core.to_jsonable_python``.
    """
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Decimal):
        if value == value.to_integral_value() and value.as_tuple().exponent >= 0:
            return int(value)
        return float(value)
    return to_jsonable_python(value)


def json_dumps(
    value: typing.Union[
        typing.List[typing.Dict[str, typing.Any]], typing.Dict[str, typing.Any]
    ],
    *,
    default: typing.Callable = None,
    indent: int = None,
    sort_keys: bool = None,
    return_bytes: bool = False,
    **kw,
) -> typing.Union[str, bytes]:
    """Practical json dumps helper function to serialize to json str
    (all default converters included, see ``json_default``).
    auto supports for ``orjson``, ``simplejson``"""

    if default is None:
        default = json_default
    dumps_params: typing.Any = {"default": default}

    if json_mod.__name__ == "orjson":
        option: int = kw.pop("option", 0)
        option_ = option
        if option_ == 0:
            if indent is not None:
                # only indent 2 is accepted
                option_ |= json_mod.OPT_INDENT_2
            if sort_keys is not None and sort_keys:
                option_ |= json_mod.OPT_SORT_KEYS

        if option_ > 0:
            dumps_params.update({"option": option_})
    else:
        if indent is not None:
            dumps_params["indent"] = indent
        if sort_keys is not None:
            dumps_params["sort_keys"] = sort_keys
        if len(kw) > 0:
            dumps_params.update(kw)
    if typing.TYPE_CHECKING:
        v: typing.Union[str, bytes]
    v = json_mod.dumps(value, **dumps_params)
    if return_bytes is True:
        if isinstance(v, str):
            v = v.encode("utf8", "strict")
    else:
        if isinstance(v, bytes):
            v = v.decode("utf8", "strict")
    return v


def json_loads(
    value: typing.Union[bytes, bytearray, str]
) -> typing.Union[
    typing.List[typing.Dict[str, typing.Any]], typing.Dict[str, typing.Any]
]:
    """Practical json dumps helper function, bytes, bytearray, and
    str input are accepted. supports for ``orjson``, ``simplejson`.

    In case of orjson, if the input exists as bytes (was read directly from a source),
    it is recommended to pass bytes. This has lower memory usage and lower latency.

    The input must be valid UTF-8."""
    if json_mod.__name__ != "orjson" and isinstance(value, (bytes, bytearray)):
        value = value.decode("utf8", "strict")

    return json_mod.loads(value)


__all__ = ["json_dumps", "json_loads", "json_default"]
