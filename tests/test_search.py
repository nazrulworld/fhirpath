# _*_ coding: utf-8 _*_
import operator
from urllib.parse import urlencode

from fhirpath.enums import MatchType
from fhirpath.enums import SortOrderType
from fhirpath.fql import Q_
from fhirpath.fql.interfaces import IGroupTerm
from fhirpath.search import Search
from fhirpath.search import SearchContext


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def test_parse_query_string():
    """ """
    params = (
        ("status:not", "completed"),
        ("status", "active"),
        ("code", "http://acme.org/conditions/codes|ha125"),
        ("probability", "gt0.8"),
        ("date", "ge2010-01-01"),
        ("date", "le2011-12-31"),
        ("alue-quantity", "5.4|http://unitsofmeasure.org|mg"),
        ("definition:below", "http:http://acme.com/some-profile"),
        ("code", "http://loinc.org|1234-5&subject.name=peter"),
        ("_sort", "status,-date,category"),
        ("_count", "1"),
        ("medication.ingredient-code", "abc"),
        ("_include", "Observation:related-target"),
    )

    result = Search.parse_query_string(urlencode(params))
    assert len(result.getall("code")) == 2
    assert len(result.getall("date")) == 2
    assert len(result.getall("medication.ingredient-code")) == 1


def test_prepare_params(engine):
    """ """
    context = SearchContext(engine, "Task")
    params = (
        ("status:not", "completed"),
        ("status", "active"),
        ("code", "http://acme.org/conditions/codes|ha125"),
        ("probability", "gt0.8"),
        ("date", "ge2010-01-01"),
        ("date", "le2011-12-31"),
        ("code", "http://loinc.org|1234-5&subject.name=peter"),
        ("_sort", "status,-date,category"),
        ("_count", "1"),
    )

    fhir_search = Search(context, params=params)
    # xxx: should be 2 as :not could be normalized? anyway we will figure it out
    assert len(fhir_search.search_params.getall("status")) == 1
    # should be gone from normal search params
    assert len(fhir_search.search_params.getall("_sort", [])) == 0
    assert "_count" not in fhir_search.search_params


def test_parameter_normalization(engine):
    """ """
    context = SearchContext(engine, "Task")
    params = (
        ("status:not", "completed"),
        ("status", "active"),
        ("code", "http://acme.org/conditions/codes|ha125"),
        ("probability", "gt0.8"),
        ("date", "ge2010-01-01"),
        ("date", "le2011-12-31"),
        ("code", "http://loinc.org|1\\,234-5&subject.name=peter"),
        ("_sort", "status,-date,category"),
        ("_count", "1"),
    )

    fhir_search = Search(context, params=params)

    field_name, value_pack, modifier = fhir_search.normalize_param("status:not")
    assert field_name == "status"
    # single valued
    assert isinstance(value_pack, tuple)
    # operator
    assert value_pack[0] == "eq"
    # actual value
    assert value_pack[1] == "completed"

    field_name, value_pack, modifier = fhir_search.normalize_param("date")
    assert modifier is None
    assert isinstance(value_pack, list)
    assert len(value_pack) == 2
    # operator
    assert value_pack[0][0] == "ge"
    # actual value
    assert value_pack[0][1] == "2010-01-01"

    # test with escape comma(,)
    field_name, value_pack, modifier = fhir_search.normalize_param("code")
    assert isinstance(value_pack, list)

    # operator
    assert value_pack[1][0] == "eq"
    # actual value
    assert value_pack[1][1] == "http://loinc.org|1\\,234-5&subject.name=peter"


def test_create_term(engine):
    """ """
    context = SearchContext(engine, "Task")
    params = (
        ("status:not", "completed"),
        ("status", "active"),
        ("code", "http://acme.org/conditions/codes|ha125"),
        ("probability", "gt0.8"),
        ("authored-on", "ge2019-07-17T19:32:59.991658"),
        ("authored-on", "le2013-01-17T19:32:59.991658"),
        ("code", "http://loinc.org|1\\,234-5&subject.name=peter"),
        ("_sort", "status,-date,category"),
        ("_count", "1"),
    )

    fhir_search = Search(context, params=params)

    field_name, value_pack, modifier = fhir_search.normalize_param("status:not")
    path_ = fhir_search.resolve_path_context(field_name)
    term = fhir_search.create_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)

    assert term.unary_operator == operator.neg
    assert term.arithmetic_operator == operator.and_
    assert term.value.value == "completed"

    field_name, value_pack, modifier = fhir_search.normalize_param("authored-on")
    path_ = fhir_search.resolve_path_context(field_name)
    term = fhir_search.create_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)

    # Now term should transformed as group of terms
    # as we see authored-on has multiple value
    assert IGroupTerm.providedBy(term) is True
    assert len(term.terms) == 2
    assert term.match_operator == MatchType.ANY
    assert term.arithmetic_operator is None


def test_create_codeableconcept_term(engine):
    """ """
    context = SearchContext(engine, "Task")
    params = (
        ("code", "http://acme.org/conditions/codes|ha125"),
        ("code", "http://terminology.hl7.org/CodeSystem/task-performer-type|"),
        ("code", "|performer"),
        ("code:text", "Performer"),
        ("code:not", "http://loinc.org|1\\,234-5&subject.name=peter"),
    )

    fhir_search = Search(context, params=params)

    field_name, value_pack, modifier = fhir_search.normalize_param("code")
    path_ = fhir_search.resolve_path_context(field_name)
    term = fhir_search.create_codeableconcept_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)

    assert IGroupTerm.providedBy(term.terms[0]) is True
    code1_group = term.terms[0]
    assert code1_group.terms[0].path.path == "Task.code.coding.system"
    assert code1_group.terms[1].path.path == "Task.code.coding.code"

    assert IGroupTerm.providedBy(term.terms[1]) is True
    assert IGroupTerm.providedBy(term.terms[2]) is True

    code2_group = term.terms[1]
    assert code2_group.terms[0].path.path == "Task.code.coding.system"

    code3_group = term.terms[2]
    assert code3_group.terms[0].path.path == "Task.code.coding.code"

    field_name, value_pack, modifier = fhir_search.normalize_param("code:text")
    path_ = fhir_search.resolve_path_context(field_name)

    term = fhir_search.create_codeableconcept_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)
    assert term.terms[0].path.path == "Task.code.text"


def test_create_identifier_term(engine):
    """ """
    context = SearchContext(engine, "Task")
    params = (
        ("identifier", "http://example.com/fhir/identifier/mrn|123456"),
        ("identifier", "http://terminology.hl7.org/CodeSystem/task-performer-type|"),
        ("identifier", "|performer"),
        ("identifier:text", "Performer"),
        ("identifier:not", "http://example.com/fhir/identifier/mrn|123456"),
    )

    fhir_search = Search(context, params=params)
    field_name, value_pack, modifier = fhir_search.normalize_param("identifier")
    path_ = fhir_search.resolve_path_context(field_name)
    term = fhir_search.create_identifier_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)

    assert IGroupTerm.providedBy(term.terms[0]) is True
    identifier_group = term.terms[0]
    assert identifier_group.terms[0].path.path == "Task.identifier.system"
    assert identifier_group.terms[1].path.path == "Task.identifier.value"

    assert term.terms[1].terms[0].path.path == "Task.identifier.system"
    assert term.terms[2].terms[0].path.path == "Task.identifier.value"

    field_name, value_pack, modifier = fhir_search.normalize_param("identifier:text")
    path_ = fhir_search.resolve_path_context(field_name)
    term = fhir_search.create_identifier_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)

    assert term.terms[0].path.path == "Task.identifier.type.text"

    field_name, value_pack, modifier = fhir_search.normalize_param("identifier:not")
    path_ = fhir_search.resolve_path_context(field_name)
    term = fhir_search.create_identifier_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)

    assert term.terms[0].unary_operator == operator.neg


def test_create_quantity_term(engine):
    """ """
    context = SearchContext(engine, "ChargeItem")
    params = (
        ("quantity", "5.4|http://unitsofmeasure.org|mg"),
        ("quantity", "lt5.1||mg"),
        ("quantity", "5.40e-3"),
        ("quantity:not", "ap5.4|http://unitsofmeasure.org|mg"),
    )
    fhir_search = Search(context, params=params)
    field_name, value_pack, modifier = fhir_search.normalize_param("quantity")
    path_ = fhir_search.resolve_path_context(field_name)
    term = fhir_search.create_quantity_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)

    assert IGroupTerm.providedBy(term.terms[0]) is True
    quantity_group = term.terms[0]
    assert quantity_group.terms[0].path.path == "ChargeItem.quantity.value"
    assert quantity_group.terms[1].path.path == "ChargeItem.quantity.system"
    assert quantity_group.terms[2].path.path == "ChargeItem.quantity.code"

    assert term.terms[1].terms[1].path.path == "ChargeItem.quantity.unit"
    assert term.terms[2].value.value == float("5.40e-3")


def test_sort_attachment(engine):
    """ """
    context = SearchContext(engine, "Task")
    params = (("status", "active"), ("_sort", "status,-modified"), ("_count", "100"))
    fhir_search = Search(context, params=params)
    builder = Q_(context.resource_name, context.engine)
    builder = fhir_search.attach_sort_terms(builder)

    assert len(builder._sort) == 2
    assert builder._sort[1].order == SortOrderType.DESC


def test_limit_attachment(engine):
    """ """
    context = SearchContext(engine, "Task")
    params = (("status", "active"), ("_sort", "status,-modified"), ("_count", "100"))
    fhir_search = Search(context, params=params)
    builder = Q_(context.resource_name, context.engine)
    builder = fhir_search.attach_limit_terms(builder)

    assert builder._limit.limit == 100
    assert builder._limit.offset == 0

    params = (
        ("status", "active"),
        ("_sort", "status,-modified"),
        ("_count", "100"),
        ("page", "4"),
    )
    fhir_search = Search(context, params=params)
    builder = Q_(context.resource_name, context.engine)
    builder = fhir_search.attach_limit_terms(builder)

    assert builder._limit.offset == 300


def test_build_query_from_search_params(engine):
    """ """
    context = SearchContext(engine, "ChargeItem")
    params = (
        ("subject", "Patient/PAT001"),
        ("quantity", "5.4|http://unitsofmeasure.org|mg"),
        ("quantity", "lt5.9||mg"),
        ("quantity", "5.40e-3"),
        ("quantity:not", "gt5.4|http://unitsofmeasure.org|mg"),
    )
    fhir_search = Search(context, params=params)
    builder = Q_(fhir_search.context.resource_name, fhir_search.context.engine)
    terms_container = list()
    for param_name in set(fhir_search.search_params):
        """ """
        normalized_data = fhir_search.normalize_param(param_name)
        fhir_search.add_term(normalized_data, terms_container)

    builder = builder.where(*terms_container)
    builder.finalize()
    query = builder.get_query()
    assert len(query.get_select()) == 1
    assert len(query.get_where()) == 3


def test_build_result(engine):
    """ """
    search_context = SearchContext(engine, "Organization")
    params = (
        ("active", "true"),
        ("_lastUpdated", "2010-05-28T05:35:56+00:00"),
        ("_profile", "http://hl7.org/fhir/Organization"),
        ("identifier", "urn:oid:2.16.528.1|91654"),
        ("type", "http://hl7.org/fhir/organization-type|prov"),
        ("address-postalcode", "9100 AA"),
        ("address", "Den Burg"),
        ("_sort", "_id"),
        ("_count", "100"),
        ("page", "4"),
    )
    fhir_search = Search(search_context, params=params)
    query_result = fhir_search.build()
    assert query_result.__class__.__name__ == "QueryResult"


def test_search_result(es_data, engine):
    """ """
    search_context = SearchContext(engine, "Organization")
    params = (
        ("active", "true"),
        ("_lastUpdated", "2010-05-28T05:35:56+00:00"),
        ("_profile", "http://hl7.org/fhir/Organization"),
        ("identifier", "urn:oid:2.16.528.1|91654"),
        ("type", "http://hl7.org/fhir/organization-type|prov"),
        ("address-postalcode", "9100 AA"),
        ("address", "Den Burg"),
    )
    fhir_search = Search(search_context, params=params)

    bundle = fhir_search()
    assert bundle.total == 1


def test_search_missing_modifier(es_data, engine):
    """ """
    search_context = SearchContext(engine, "Organization")
    params = (
        ("active:missing", "false"),
    )
    fhir_search = Search(search_context, params=params)

    bundle = fhir_search()
    assert len(bundle.entry) == 1
