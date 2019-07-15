#!/usr/bin/env python
# _*_ coding: utf-8 _*_
"""Tests for `fhirpath` package."""
import operator
from datetime import datetime

import pytest
import pytz

from fhirpath.fql.expressions import G_
from fhirpath.fql.expressions import T_
from fhirpath.fql.expressions import V_
from fhirpath.fql.expressions import and_
from fhirpath.fql.expressions import exists_
from fhirpath.fql.expressions import in_
from fhirpath.fql.expressions import not_exists_
from fhirpath.fql.expressions import not_in_
from fhirpath.fql.expressions import or_
from fhirpath.fql.interfaces import IExistsTerm
from fhirpath.fql.interfaces import IGroupTerm
from fhirpath.fql.interfaces import IQuery
from fhirpath.fql.interfaces import IQueryResult
from fhirpath.fql.interfaces import ITerm
from fhirpath.fql.queries import QueryBuilder
from fhirpath.fql.types import Term
from fhirpath.fql.types import TermValue
from fhirpath.storage import PATH_INFO_STORAGE
from fhirpath.utils import import_string
from fhirpath.utils import lookup_fhir_class_path


def test_term_normal(engine):
    """Sample pytest test function with the pytest fixture as an argument."""
    term = Term("Patient.active", "false")
    term.finalize(engine)

    assert term.value() is False
    assert term.arithmetic_operator == operator.and_

    term = Term("Patient.address.line", "Lane 1")
    term.finalize(engine)

    assert term.path.context.multiple is True
    assert isinstance(term.value(), str)

    # test parent path (Patient.address) context also created.
    pathname = "Patient.address"
    try:
        context = PATH_INFO_STORAGE.get(engine.fhir_release.value).get(pathname)
    except KeyError:
        pytest.fail("Code should not come here! as cache should be already created")

    address_model = import_string(lookup_fhir_class_path("Address"))

    assert context.multiple is True
    assert context.type_class == address_model
    assert context.prop_name == "address"
    assert context.optional is True


def test_term_complex_operator(engine):
    """ """
    term = Term("Patient.meta.lastUpdated")
    value = TermValue(datetime.now().replace(tzinfo=pytz.UTC).isoformat())
    term = term >= value
    term.finalize(engine)

    assert term.comparison_operator == operator.ge
    assert isinstance(term.value(), datetime)


def test_expression_add(engine):
    """ """
    term = and_("Patient.name.given", "Krog")
    term.finalize(engine)
    assert ITerm.providedBy(term)
    assert term.arithmetic_operator == operator.and_
    assert term.path.context.multiple is True

    term = T_("Patient.name.period.start")
    term = and_(-term, datetime.now().isoformat(timespec="seconds"))
    term.finalize(engine)
    assert term.unary_operator == operator.neg

    term = T_("Patient.name.period.start")
    group = G_(term <= datetime.now().isoformat(timespec="seconds"))
    group = and_(group)

    group.finalize(engine)

    assert IGroupTerm.providedBy(group) is True
    assert len(group.terms) == 1
    assert group.terms[0]._finalized is True


def test_expression_or(engine):
    """ """
    term = or_("Task.for.reference", "Patient/PAT-001")
    term.finalize(engine)
    assert ITerm.providedBy(term)
    assert term.arithmetic_operator == operator.or_
    assert term.path.context.parent.prop_name == "for_fhir"

    term = T_("Patient.name.period.start")
    term = or_(-term, datetime.now().isoformat(timespec="seconds"))
    term.finalize(engine)
    assert term.unary_operator == operator.neg

    term = T_("Patient.name.period.start")
    group = G_(term <= datetime.now().isoformat(timespec="seconds"))
    group = or_(group)

    group.finalize(engine)

    assert len(group.terms) == 1
    assert group.terms[0]._finalized is True


def test_expression_existence(engine):
    """ """
    term = exists_("Patient.name.period.start")
    term.finalize(engine)

    assert IExistsTerm.providedBy(term) is True
    assert term.unary_operator == operator.pos

    # test not exists
    term = not_exists_("Task.for.reference")
    term.finalize(engine)
    assert term.unary_operator == operator.neg

    # Test from Term
    term = T_("Task.for.reference", "Patient/PAT-001")
    term = exists_(term)
    term.finalize(engine)

    assert IExistsTerm.providedBy(term) is True


def test_expression_in(engine):
    """ """
    term = in_("Organization.telecom.rank", 67)
    term += 78
    term += (54, 89)
    term.finalize(engine)
    assert len(term.value) == 4

    # test not in
    term = not_in_("Task.for.reference", "Patient/PAT-002")
    term = term + "Patient/PAT-001"
    term.finalize(engine)

    assert term.unary_operator == operator.neg
    assert len(term.value) == 2


def test_expression_in_exception(engine):
    """ """
    # Test not same type value
    term = in_(
        "Patient.name.period.start", datetime.now().replace(microsecond=0).isoformat()
    )
    term += "NON_DATE_VALUE"

    with pytest.raises(ValueError):
        assert term.finalize(engine)


def test_complex_expression(engine):
    """ """
    term = T_("Organization.telecom.rank")
    value = V_("26")
    term = term >= (-value)
    term.finalize(engine)

    assert term.unary_operator == operator.neg


def test_query_builder(engine):
    """ """
    builder = (
        QueryBuilder(engine)
        .from_("Patient")
        .select("*")
        .where(**{"Patient.managingOrganization.reference": "Organization/ORG-011"})
        .sort("Patient.id")
        .limit(0, 100)
    )
    builder.finalize(engine)

    assert IQueryResult.providedBy(builder())
    query = builder.get_query()
    assert IQuery.providedBy(query)

    assert query.get_limit().empty is False
