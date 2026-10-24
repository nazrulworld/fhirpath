# _*_ coding: utf-8 _*_
"""Search behaviour required by the FHIR search specification, without a
search backend: escaping, modifier validation, reference values and the
searchset Bundle links."""

import pytest
from pytest import raises

from fhirpath.search.engine import (
    EngineResult,
    EngineResultBody,
    EngineResultHeader,
)
from fhirpath.search.exceptions import ValidationError
from fhirpath.search.search import (
    Search,
    SearchContext,
    split_escaped,
    unescape_value,
    validate_escapes,
)
from tests._utils import TestElasticsearchEngine


@pytest.fixture
def offline_engine():
    return TestElasticsearchEngine(None)


def links(bundle):
    return {link["relation"]: link["url"] for link in bundle["link"]}


# -------------------------------------------------------------------- escaping


def test_split_escaped_keeps_escapes():
    assert split_escaped(r"a\,b,c", ",") == [r"a\,b", "c"]
    assert split_escaped(r"a\|b|c", "|") == [r"a\|b", "c"]
    assert split_escaped(r"a\\,b", ",") == [r"a\\", "b"]
    assert split_escaped("a$b", "$") == ["a", "b"]


def test_unescape_value():
    assert unescape_value(r"a\,b") == "a,b"
    assert unescape_value(r"a\$b\|c\\d") == "a$b|c\\d"
    assert unescape_value("plain") == "plain"


def test_illegal_escape_is_rejected():
    validate_escapes(r"a\,b\$c\|d\\e")
    for bad in (r"a\b", "a\\"):
        with raises(ValidationError, match="Illegal escape sequence"):
            validate_escapes(bad)


def test_escaped_values_are_not_split(offline_engine):
    context = SearchContext(offline_engine, "Patient")
    _, value, _ = context.normalize_param("family", [r"Smith\,Jones,Doe"])[0]
    assert value == (None, [("eq", r"Smith\,Jones"), ("eq", "Doe")])

    with raises(ValidationError, match="Illegal escape sequence"):
        context.normalize_param("family", [r"Smith\x"])


def test_escaped_pipe_in_token(offline_engine):
    context = SearchContext(offline_engine, "Patient")
    search = Search(context, params=(("identifier", r"http://a|b\|c"),))
    (term,) = search.attach_where_terms(_Builder())
    system, value = term.terms
    assert system.value.raw == "http://a"
    assert value.value.raw == "b|c"


class _Builder:
    def where(self, *terms):
        return terms


# ------------------------------------------------------------------- modifiers


@pytest.mark.parametrize(
    "param",
    [
        "code:in",
        "code:not-in",
        "identifier:of-type",
        "code:code-text",
        "code:unknown",
        "value-quantity:exact",
        "date:contains",
        "status:identifier",
    ],
)
def test_unsupported_modifier_is_rejected(offline_engine, param):
    context = SearchContext(offline_engine, "Observation")
    with raises(ValidationError, match="is not supported"):
        context.normalize_param(param, ["x"])


def test_composite_takes_no_modifier(offline_engine):
    context = SearchContext(offline_engine, "Observation")
    with raises(ValidationError, match="does not take modifiers"):
        context.normalize_param("code-value-quantity:missing", ["a$1"])


def test_type_modifier(offline_engine):
    context = SearchContext(offline_engine, "Observation")
    path, value, modifier = context.normalize_param("subject:Patient", ["23"])[0]
    assert value == ("eq", "Patient/23")
    assert modifier is None

    _, value, _ = context.normalize_param("subject:Patient", ["23,Patient/24"])[0]
    assert value == (None, [("eq", "Patient/23"), ("eq", "Patient/24")])

    with raises(ValidationError, match="is not a target type"):
        context.normalize_param("subject:Medication", ["23"])
    with raises(ValidationError, match="expects a resource id"):
        context.normalize_param("subject:Patient", ["Group/23"])


# ------------------------------------------------------------ reference values


def test_plain_id_is_a_reference_to_every_target(offline_engine):
    context = SearchContext(offline_engine, "Observation")
    _, value, _ = context.normalize_param("subject", ["23"])[0]
    targets = context.definitions[0].subject.target
    assert value == (None, [("eq", f"{t}/23") for t in targets])

    # typed, versioned and absolute references are kept as given
    for given in ("Patient/23", "Patient/23/_history/2", "http://x.org/Patient/23"):
        _, value, _ = context.normalize_param("subject", [given])[0]
        assert value == ("eq", given)


def test_resolve_is_restricts_plain_ids(offline_engine):
    # R4: Observation.patient = Observation.subject.where(resolve() is Patient)
    context = SearchContext(offline_engine, "Observation")
    _, value, _ = context.normalize_param("patient", ["23"])[0]
    assert value == ("eq", "Patient/23")


# ------------------------------------------------------------------ the Bundle


def make_result(total):
    return EngineResult(EngineResultHeader(total=total), EngineResultBody())


def test_paging_links_use_page(offline_engine):
    bundle = offline_engine.wrapped_with_bundle(
        make_result(250),
        as_json=True,
        applied_params={"family": "Doe", "_count": "100", "page": "2"},
    )
    found = links(bundle)
    assert set(found) == {"self", "first", "previous", "next", "last"}
    assert "page=1" in found["first"] and "page=1" in found["previous"]
    assert "page=3" in found["next"] and "page=3" in found["last"]
    assert all("family=Doe" in url for url in found.values())

    # the links can be followed: ``page`` and ``_count`` are understood
    context = SearchContext(offline_engine, "Patient")
    search = Search(context, query_string=found["next"].split("?", 1)[1])
    assert search.result_params["page"] == 3
    assert search.result_params["_count"] == 100


def test_last_page_has_no_next(offline_engine):
    bundle = offline_engine.wrapped_with_bundle(
        make_result(250), as_json=True, applied_params={"_count": "100", "page": "3"}
    )
    assert set(links(bundle)) == {"self", "first", "previous"}


def test_no_paging_links_for_a_single_page(offline_engine):
    bundle = offline_engine.wrapped_with_bundle(
        make_result(5), as_json=True, applied_params={"_count": "10"}
    )
    assert set(links(bundle)) == {"self"}


def test_self_link_shows_applied_params(offline_engine):
    context = SearchContext(offline_engine, "Patient")
    search = Search(context, query_string="family=Doe&given=&_count=10")
    bundle = search.empty_response(as_json=True)
    self_url = links(bundle)["self"]
    assert "family=Doe" in self_url and "_count=10" in self_url
    # empty values are ignored, so they are not reported as applied
    assert "given" not in self_url
