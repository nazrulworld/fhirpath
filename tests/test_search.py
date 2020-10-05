# _*_ coding: utf-8 _*_
import re
from urllib.parse import urlencode
from pytest import raises

from fhirpath import Q_
from fhirpath.enums import FHIR_VERSION
from fhirpath.enums import OPERATOR
from fhirpath.enums import MatchType
from fhirpath.enums import SortOrderType
from fhirpath.interfaces.fql import IGroupTerm
from fhirpath.search import Search
from fhirpath.search import SearchContext
from fhirpath.exceptions import ValidationError

from fhir.resources.patient import Patient
from fhir.resources.observation import Observation
from fhir.resources.practitioner import Practitioner
from fhir.resources.medicationrequest import MedicationRequest


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def test_params_definition(engine):
    """ """
    definition = SearchContext(
        engine=engine, resource_type="Organization"
    ).get_parameters_definition(FHIR_VERSION.R4)
    assert definition[0].name.expression == "Organization.name"


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

    # TODO we need the [0] because normalize_param returns a list to handle the
    # case where we search on several resource types
    path_, value_pack, modifier = context.normalize_param("status:not", ["completed"])[
        0
    ]
    # single valued
    assert isinstance(value_pack, tuple)
    # OPERATOR
    assert value_pack[0] == "eq"
    # actual value
    assert value_pack[1] == "completed"

    field_name, value_pack, modifier = context.normalize_param(
        "authored-on", ["ge2010-01-01", "le2011-12-31"]
    )[0]
    assert modifier is None
    assert isinstance(value_pack, list)
    assert len(value_pack) == 2
    # OPERATOR
    assert value_pack[0][0] == "ge"
    # actual value
    assert value_pack[0][1] == "2010-01-01"

    # test with escape comma(,)
    field_name, value_pack, modifier = context.normalize_param(
        "code",
        [
            "http://acme.org/conditions/codes|ha125",
            "http://loinc.org|1\\,234-5&subject.name=peter",
        ],
    )[0]
    assert isinstance(value_pack, list)
    # OPERATOR
    assert value_pack[1][0] == "eq"
    # actual value
    assert value_pack[1][1] == "http://loinc.org|1\\,234-5&subject.name=peter"

    # Test IN Operator
    field_name, value_pack, modifier = context.normalize_param(
        "_lastUpdated", ["le2019-09-12T13:20:44+0000,2018-09-12T13:20:44+0000"]
    )[0]
    assert isinstance(value_pack, tuple)
    operator_, values = value_pack
    assert operator_ is None
    assert len(values) == 2
    assert values[0][1] == "2019-09-12T13:20:44+0000"

    # Test AND+IN Operator
    field_name, value_pack, modifier = context.normalize_param(
        "_id", ["567890", "998765555554678,45555555555567"]
    )[0]
    assert isinstance(value_pack, list)
    assert isinstance(value_pack[0], tuple)
    assert isinstance(value_pack[1][1], list)


def test_composite_parameter_normalization(engine):
    """ """
    context = SearchContext(engine, "ChargeItemDefinition")
    normalize_value = context.normalize_param("context-type-quantity", ["HL7&99"])[0]
    assert len(normalize_value) == 2
    assert normalize_value[0][0].path.endswith(".code")
    # value.as(Quantity) | value.as(Range)
    assert len(normalize_value[1]) == 2
    assert normalize_value[1][1][0].path.endswith(".valueRange") is True

    context = SearchContext(engine, "Observation")
    normalize_value = context.normalize_param(
        "code-value-quantity", ["http://loinc.org|11557-6&6.2"]
    )[0]
    assert isinstance(normalize_value[1], tuple)


def test_parameter_normalization_with_space_as(engine):
    """ """
    context = SearchContext(engine, "MedicationRequest")

    path_, value_pack, _ = context.normalize_param(
        "code", ["http://acme.org/conditions/codes|ha125"]
    )[0]
    # single valued
    assert isinstance(value_pack, tuple)
    assert path_.path == "MedicationRequest.medicationCodeableConcept"


def test_parameter_normalization_empty_value(engine):
    context = SearchContext(engine, "MedicationRequest")
    # normalize a param with an empty value: it should be ignored
    params = context.normalize_param("code", [""])
    assert len(params) == 0


def test_parameter_normalization_prefix(engine):
    """ """
    # number
    context = SearchContext(engine, "MolecularSequence")
    _, value_pack, _ = context.normalize_param("variant-end", ["gt1"])[0]
    assert value_pack == ("gt", "1")

    # quantity
    context = SearchContext(engine, "Substance")
    _, value_pack, _ = context.normalize_param("quantity", ["ne1"])[0]
    assert value_pack == ("ne", "1")

    # date
    context = SearchContext(engine, "Patient")
    _, value_pack, _ = context.normalize_param("death-date", ["lt1980"])[0]
    assert value_pack == ("lt", "1980")

    # string
    _, value_pack, _ = context.normalize_param("name", ["leslie"])[0]
    assert value_pack == ("eq", "leslie")

    # token
    _, value_pack, _ = context.normalize_param("language", ["nepalese"])[0]
    assert value_pack == ("eq", "nepalese")

    # reference
    _, value_pack, _ = context.normalize_param("organization", ["necker"])[0]
    assert value_pack == ("eq", "necker")


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

    path_, value_pack, modifier = context.normalize_param("status:not", ["completed"])[
        0
    ]
    term = fhir_search.create_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)

    assert term.unary_operator == OPERATOR.neg
    assert term.arithmetic_operator == OPERATOR.and_
    assert term.value.value == "completed"

    path_, value_pack, modifier = context.normalize_param(
        "authored-on", ["ge2019-07-17T19:32:59.991658", "le2013-01-17T19:32:59.991658"]
    )[0]
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

    path_, value_pack, modifier = context.normalize_param(
        "code",
        [
            "http://acme.org/conditions/codes|ha125",
            "http://terminology.hl7.org/CodeSystem/task-performer-type|",
            "|performer",
        ],
    )[0]
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

    path_, value_pack, modifier = context.normalize_param("code:text", ["Performer"])[0]

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
    path_, value_pack, modifier = context.normalize_param(
        "identifier",
        [
            "http://example.com/fhir/identifier/mrn|123456",
            "http://terminology.hl7.org/CodeSystem/task-performer-type|",
            "|performer",
        ],
    )[0]
    term = fhir_search.create_identifier_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)

    assert IGroupTerm.providedBy(term.terms[0]) is True
    identifier_group = term.terms[0]
    assert identifier_group.terms[0].path.path == "Task.identifier.system"
    assert identifier_group.terms[1].path.path == "Task.identifier.value"

    assert term.terms[1].terms[0].path.path == "Task.identifier.system"
    assert term.terms[2].terms[0].path.path == "Task.identifier.value"

    path_, value_pack, modifier = context.normalize_param(
        "identifier:text", ["Performer"]
    )[0]
    term = fhir_search.create_identifier_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)

    assert term.terms[0].path.path == "Task.identifier.type.text"

    path_, value_pack, modifier = context.normalize_param(
        "identifier:not", ["http://example.com/fhir/identifier/mrn|123456"]
    )[0]
    term = fhir_search.create_identifier_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)

    assert term.terms[0].unary_operator == OPERATOR.neg


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
    path_, value_pack, modifier = context.normalize_param(
        "quantity", ["5.4|http://unitsofmeasure.org|mg", "lt5.1||mg", "5.40e-3"]
    )[0]
    term = fhir_search.create_quantity_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)

    assert IGroupTerm.providedBy(term.terms[0]) is True
    quantity_group = term.terms[0]
    assert quantity_group.terms[0].path.path == "ChargeItem.quantity.value"
    assert quantity_group.terms[1].path.path == "ChargeItem.quantity.system"
    assert quantity_group.terms[2].path.path == "ChargeItem.quantity.code"

    assert term.terms[1].terms[1].path.path == "ChargeItem.quantity.unit"
    assert float(term.terms[2].value.value) == float("5.40e-3")


def test_sa_term(engine):
    """ """
    context = SearchContext(engine, "Organization")
    params = (("_id:below", "fo"),)

    fhir_search = Search(context, params=params)

    path_, value_pack, modifier = context.normalize_param("_id:below", ["fo"])[0]
    term = fhir_search.create_term(path_, value_pack, modifier)
    term.finalize(fhir_search.context.engine)

    assert term.comparison_operator == OPERATOR.sa


def test_sort_attachment(engine):
    """ """
    context = SearchContext(engine, "Task")
    params = (("status", "active"), ("_sort", "status,-modified"), ("_count", "100"))
    fhir_search = Search(context, params=params)
    builder = Q_(context.resource_types, context.engine)
    builder = fhir_search.attach_sort_terms(builder)

    assert len(builder._sort) == 2
    assert builder._sort[1].order == SortOrderType.DESC


def test_limit_attachment(engine):
    """ """
    context = SearchContext(engine, "Task")
    params = (("status", "active"), ("_sort", "status,-modified"), ("_count", "100"))
    fhir_search = Search(context, params=params)
    builder = Q_(context.resource_types, context.engine)
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
    builder = Q_(context.resource_types, context.engine)
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
    builder = Q_(fhir_search.context.resource_types, fhir_search.context.engine)
    terms_container = list()
    for param_name in set(fhir_search.search_params):
        raw_value = list(fhir_search.search_params.getall(param_name, []))
        normalized_data = context.normalize_param(param_name, raw_value)
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


def test_search_result_as_json(es_data, engine):
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

    bundle = fhir_search(as_json=True)
    assert bundle["total"] == 1
    assert isinstance(bundle["entry"][0], dict)


def test_search_missing_modifier(es_data, engine):
    """ """
    search_context = SearchContext(engine, "Organization")
    params = (("active:missing", "false"),)
    fhir_search = Search(search_context, params=params)

    bundle = fhir_search()
    assert len(bundle.entry) == 1


def test_in_search(es_data, engine):
    """ """
    search_context = SearchContext(engine, "Organization")
    params = (
        ("active", "true"),
        ("address", "Den Burg,Fake Lane"),
        ("_profile", "http://hl7.org/fhir/Organization,http://another"),
    )
    fhir_search = Search(search_context, params=params)

    bundle = fhir_search()
    assert bundle.total == 1


def test_composite_param_search(es_data, engine):
    """ """
    search_context = SearchContext(engine, "Observation")
    params = (("code-value-quantity", "http://loinc.org|718-7&7.2"),)
    fhir_search = Search(search_context, params=params)

    bundle = fhir_search()
    assert bundle.total == 1


def test_codeableconcept_with_not_modifier(es_data, engine):
    """ """
    # test with single
    search_context = SearchContext(engine, "ChargeItem")
    params = (("code:not", "http://snomed.info/sct|01510"),)
    fhir_search = Search(search_context, params=params)

    bundle = fhir_search()
    assert bundle.total == 0

    params = (("code:not", "http://snomed.info/sct|01510,http://lonic.org|1510-9"),)
    fhir_search = Search(search_context, params=params)

    bundle = fhir_search()
    assert bundle.total == 0


def test_search_result_with_below_modifier(es_data, engine):
    """ """
    search_context = SearchContext(engine, "Organization")
    params = (("name:below", "Burge"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1
    # little bit complex
    search_context = SearchContext(engine, "Patient")
    params = (("identifier:below", "|2403"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    params = (("given:below", "Eel,Eve"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    params = (("gender:below", "ma,naz"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1


def test_search_result_with_above_modifier(es_data, engine):
    """ """
    # little bit complex
    search_context = SearchContext(engine, "Patient")
    params = (("identifier:above", "|0002"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    search_context = SearchContext(engine, "Organization")
    params = (("name:above", "Medical Center"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1


def test_search_result_with_contains_modifier(es_data, engine):
    """ """
    # little bit complex
    search_context = SearchContext(engine, "Patient")
    params = (("identifier:contains", "|365"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    params = (("given:contains", "ect"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    search_context = SearchContext(engine, "Organization")
    params = (("name:contains", "Medical"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1


def test_search_result_with_exact_modifier(es_data, engine):
    """ """
    search_context = SearchContext(engine, "Patient")

    params = (("family:exact", "Saint"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    params = (("family:exact", "Other"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    params = (("family:exact", "Sain"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    params = (("family:exact", "saint"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    params = (("family:exact", "Sàint"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0


def test_issue9_multiple_negative_terms_not_working(es_data, engine):
    """https://github.com/nazrulworld/fhirpath/issues/9"""
    search_context = SearchContext(engine, "Task")
    params = (("status:not", "ready,cancelled"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1


def test_search_negative_address(es_data, engine):
    """ """
    search_context = SearchContext(engine, "Organization")
    params = (("address:not", "Den Burg"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    params = (("address-postalcode:not", "9105 PZ"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0
    params = (
        (
            "_profile:not",
            "urn:oid:002.160,urn:oid:002.260,http://hl7.org/fhir/Other",
        ),
    )
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0


def test_issue8_without_param(es_data, engine):
    """ """
    search_context = SearchContext(engine, "Organization")
    fhir_search = Search(search_context)
    bundle = fhir_search()
    assert bundle.total == 1


def test_search_include(es_data, engine):
    # typed _include
    search_context = SearchContext(engine, "Observation")
    params = (("_include", "Observation:subject:Patient"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1
    assert len(bundle.entry) == 2
    assert isinstance(bundle.entry[0].resource, Observation)
    assert isinstance(bundle.entry[1].resource, Patient)

    # untyped _include
    search_context = SearchContext(engine, "Observation")
    params = (("_include", "Observation:subject"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1
    assert len(bundle.entry) == 2
    assert isinstance(bundle.entry[0].resource, Observation)
    assert isinstance(bundle.entry[1].resource, Patient)

    # many types
    search_context = SearchContext(engine, "Observation")
    params = (
        ("_include", "Observation:subject:Patient"),
        ("_include", "Observation:subject:Location"),
    )
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1
    assert len(bundle.entry) == 2
    assert isinstance(bundle.entry[0].resource, Observation)
    assert isinstance(bundle.entry[1].resource, Patient)

    # .where(resolve() is Resource) constraint
    search_context = SearchContext(engine, "Observation")
    params = (("_include", "Observation:patient"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1
    assert len(bundle.entry) == 2

    # many references
    search_context = SearchContext(engine, "Observation")
    params = (
        ("_include", "Observation:subject:Patient"),
        ("_include", "Observation:performer"),
    )
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1
    assert len(bundle.entry) == 3
    assert isinstance(bundle.entry[0].resource, Observation)
    assert isinstance(bundle.entry[1].resource, Patient)
    assert isinstance(bundle.entry[2].resource, Practitioner)

    # bad syntax
    search_context = SearchContext(engine, "Observation")
    params = (("_include", "subject"),)
    fhir_search = Search(search_context, params=params)
    with raises(
        ValidationError,
        match=re.escape(
            "bad _include param 'subject', "
            "should be Resource:search_param[:target_type]"
        ),
    ):
        fhir_search()

    # bad searchparam
    search_context = SearchContext(engine, "Observation")
    params = (("_include", "Observation:category"),)
    fhir_search = Search(search_context, params=params)
    with raises(
        ValidationError,
        match=re.escape(
            "search parameter Observation.category "
            "must be of type 'reference', got token"
        ),
    ):
        fhir_search()

    # unknown searchparam
    search_context = SearchContext(engine, "Observation")
    params = (("_include", "Observation:unknown"),)
    fhir_search = Search(search_context, params=params)
    with raises(
        ValidationError,
        match=re.escape(
            "No search definition is available for search "
            "parameter ``unknown`` on Resource ``Observation``."
        ),
    ):
        fhir_search()

    # bad target
    search_context = SearchContext(engine, "Observation")
    params = (("_include", "Observation:subject:DocumentReference"),)
    fhir_search = Search(search_context, params=params)
    with raises(
        ValidationError,
        match=re.escape(
            "the search param Observation.subject may refer "
            "to Group, Device, Patient, Location"
            ", not to DocumentReference"
        ),
    ):
        fhir_search()


def test_search_has(es_data, engine):
    # found
    search_context = SearchContext(engine, "Patient")
    params = (("_has:Observation:patient:code", "718-7"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1
    assert isinstance(bundle.entry[0].resource, Patient)

    # not found
    search_context = SearchContext(engine, "Patient")
    params = (("_has:Observation:patient:code", "XXX-YYY"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    # bad syntax
    search_context = SearchContext(engine, "Patient")
    params = (("_has:Observation:patient", "718-7"),)
    fhir_search = Search(search_context, params=params)
    with raises(
        ValidationError,
        match=re.escape(
            "bad _has param '_has:Observation:patient', "
            "should be _has:Resource:ref_search_param:value_search_param=value"
        ),
    ):
        fhir_search()

    # bad searchparam
    search_context = SearchContext(engine, "Patient")
    params = (("_has:Observation:category:code", "something"),)
    fhir_search = Search(search_context, params=params)
    with raises(
        ValidationError,
        match=re.escape(
            "search parameter Observation.category must be "
            "of type 'reference', got token"
        ),
    ):
        fhir_search()

    # unknown searchparam
    search_context = SearchContext(engine, "Patient")
    params = (("_has:Observation:unknown:code", "something"),)
    fhir_search = Search(search_context, params=params)
    with raises(
        ValidationError,
        match=re.escape(
            "No search definition is available for search "
            "parameter ``unknown`` on Resource ``Observation``."
        ),
    ):
        fhir_search()

    # bad target
    search_context = SearchContext(engine, "Patient")
    params = (("_has:Observation:encounter:identifier", "something"),)
    fhir_search = Search(search_context, params=params)
    with raises(
        ValidationError,
        match=re.escape(
            "invalid reference Observation.encounter (Encounter,EpisodeOfCare) "
            "in the current search context (Patient)"
        ),
    ):
        fhir_search()


def test_search_revinclude(es_data, engine):
    # untyped
    search_context = SearchContext(engine, "Patient")
    params = (("_revinclude", "Observation:subject"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1
    assert len(bundle.entry) == 2
    assert isinstance(bundle.entry[0].resource, Patient)
    assert isinstance(bundle.entry[1].resource, Observation)

    # typed
    search_context = SearchContext(engine, "Patient")
    params = (("_revinclude", "Observation:subject:Patient"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1
    assert len(bundle.entry) == 2
    assert isinstance(bundle.entry[0].resource, Patient)
    assert isinstance(bundle.entry[1].resource, Observation)

    # no results
    search_context = SearchContext(engine, "Location")
    params = (("_revinclude", "Observation:subject"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0
    assert len(bundle.entry) == 0

    # double _revinclude
    search_context = SearchContext(engine, "Patient")
    params = (
        ("_revinclude", "Observation:subject"),
        ("_revinclude", "MedicationRequest:subject"),
    )
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1
    assert len(bundle.entry) == 3
    assert isinstance(bundle.entry[0].resource, Patient)
    assert isinstance(bundle.entry[1].resource, Observation)
    assert isinstance(bundle.entry[2].resource, MedicationRequest)

    # with _has
    search_context = SearchContext(engine, "Patient")
    params = (
        ("_has:Observation:patient:code", "718-7"),
        ("_revinclude", "Observation:subject"),
    )
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1
    assert len(bundle.entry) == 2
    assert isinstance(bundle.entry[0].resource, Patient)
    assert isinstance(bundle.entry[1].resource, Observation)

    # bad syntax
    search_context = SearchContext(engine, "Patient")
    params = (("_revinclude", "subject"),)
    fhir_search = Search(search_context, params=params)
    with raises(
        ValidationError,
        match=re.escape(
            "bad _revinclude param 'subject', should be "
            "Resource:search_param[:target_type]"
        ),
    ):
        fhir_search()

    # bad syntax
    search_context = SearchContext(engine, "Patient")
    params = (("_revinclude", "Observation:subject:too:long"),)
    fhir_search = Search(search_context, params=params)
    with raises(
        ValidationError,
        match=re.escape(
            "bad _revinclude param 'Observation:subject:too:long', "
            "should be Resource:search_param[:target_type]"
        ),
    ):
        fhir_search()

    # bad searchparam
    search_context = SearchContext(engine, "Patient")
    params = (("_revinclude", "Observation:category"),)
    fhir_search = Search(search_context, params=params)
    with raises(
        ValidationError,
        match=re.escape(
            "search parameter Observation.category must "
            "be of type 'reference', got token"
        ),
    ):
        fhir_search()

    # unknown searchparam
    search_context = SearchContext(engine, "Patient")
    params = (("_revinclude", "Observation:unknown:code"),)
    fhir_search = Search(search_context, params=params)
    with raises(
        ValidationError,
        match=re.escape(
            "No search definition is available for search "
            "parameter ``unknown`` on Resource ``Observation``."
        ),
    ):
        fhir_search()

    # bad target
    search_context = SearchContext(engine, "Patient")
    params = (("_revinclude", "Observation:encounter:identifier"),)
    fhir_search = Search(search_context, params=params)
    with raises(
        ValidationError,
        match=re.escape(
            "invalid reference Observation.encounter (Encounter,EpisodeOfCare) "
            "in the current search context (Patient)"
        ),
    ):
        fhir_search()


def test_search_fhirpath_reference_analyzer(es_data, engine):
    """ References need to be indexed in a special way in order to be found"""
    search_context = SearchContext(engine, "Observation")

    # search Normal
    params = (("subject", "Patient/19c5245f-89a8-49f8-b244-666b32adb92e"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    # search by ID
    params = (("subject", "19c5245f-89a8-49f8-b244-666b32adb92e"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    # search by (wrong) ID
    params = (("subject", "29c5245f-89a8-49f8-b244-666b32adb92e"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    # search by resource_type (should not find anything)
    params = (("subject", "Patient"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    # test negative: search by last part
    params = (("subject:not", "19c5245f-89a8-49f8-b244-666b32adb92e"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    # test full URI with wrong last part
    params = (("subject", "Patient/fake245f-89a8-49f8-b244-666b32adb92e"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    # test full URI with wrong first part
    params = (("subject", "Device/19c5245f-89a8-49f8-b244-666b32adb92e"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    # search by resource_type as prefix
    params = (("subject:below", "Patient"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    # search by ID as suffix
    params = (("subject:above", "19c5245f-89a8-49f8-b244-666b32adb92e"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1


def test_searchparam_type_date_period_eq(es_data, engine):
    search_context = SearchContext(engine, "Encounter")
    params = (("date", "eq2015-01-17"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    search_context = SearchContext(engine, "CarePlan")
    params = (("date", "eq2017-06-01"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1


def test_searchparam_type_date_period_ne(es_data, engine):
    search_context = SearchContext(engine, "Encounter")
    params = (("date", "ne2015-01-17"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    search_context = SearchContext(engine, "CarePlan")
    params = (("date", "ne2017-06-01T17:00:00"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    params = (("date", "ne2017-06-01"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0


def test_searchparam_type_date_period_gt(es_data, engine):
    search_context = SearchContext(engine, "Encounter")
    params = (("date", "gt2015-01-20"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    search_context = SearchContext(engine, "CarePlan")
    params = (("date", "gt2017-06-01T17:00:00"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    params = (("date", "gt2017-06-02"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0


def test_searchparam_type_date_period_lt(es_data, engine):
    search_context = SearchContext(engine, "Encounter")
    params = (("date", "lt2015-01-20"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    search_context = SearchContext(engine, "CarePlan")
    params = (("date", "lt2017-06-01T15:00:00"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0


def test_searchparam_type_date_period_ge(es_data, engine):
    search_context = SearchContext(engine, "Encounter")
    params = (("date", "ge2015-01-20"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    search_context = SearchContext(engine, "CarePlan")
    params = (("date", "ge2017-06-01T17:00:00"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    params = (("date", "ge2017-06-01"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    params = (("date", "ge2017-06-02"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0


def test_searchparam_type_date_period_le(es_data, engine):
    search_context = SearchContext(engine, "Encounter")
    params = (("date", "le2015-01-20"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    search_context = SearchContext(engine, "CarePlan")
    params = (("date", "le2017-06-01T16:00:00"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    params = (("date", "le2017-06-01T15:00:00"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0


def test_searchparam_type_date_period_sa(es_data, engine):
    search_context = SearchContext(engine, "CarePlan")
    params = (("date", "sa2017-06-01T17:00:00"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    params = (("date", "sa2017-06-01T12:00:00"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1


def test_searchparam_type_date_period_eb(es_data, engine):
    search_context = SearchContext(engine, "Encounter")
    params = (("date", "eb2019-01-20"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    search_context = SearchContext(engine, "CarePlan")
    params = (("date", "eb2017-06-01T18:00:00"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    params = (("date", "eb2019-01-20"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1


def test_searchparam_type_date_period_ap(es_data, engine):
    search_context = SearchContext(engine, "Encounter")
    params = (("date", "ap2015-01-17T16:00:00"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    params = (("date", "ap2015-01-16T16:00:00"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0

    params = (("date", "ap2019-01-20"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    search_context = SearchContext(engine, "CarePlan")
    params = (("date", "ap2017-06-01T17:00:00"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 1

    params = (("date", "ap2017-06-01T19:00:00"),)
    fhir_search = Search(search_context, params=params)
    bundle = fhir_search()
    assert bundle.total == 0
