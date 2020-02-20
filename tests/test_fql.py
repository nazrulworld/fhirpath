#!/usr/bin/env python
# _*_ coding: utf-8 _*_
"""Tests for `fhirpath` package."""
from datetime import datetime

import pytest
import pytz

from fhirpath.enums import OPERATOR
from fhirpath.enums import WhereConstraintType
from fhirpath.fql.expressions import G_
from fhirpath.fql.expressions import T_
from fhirpath.fql.expressions import V_
from fhirpath.fql.expressions import and_
from fhirpath.fql.expressions import exists_
from fhirpath.fql.expressions import in_
from fhirpath.fql.expressions import not_exists_
from fhirpath.fql.expressions import not_in_
from fhirpath.fql.expressions import or_
from fhirpath.fql.expressions import sa_
from fhirpath.fql.types import ElementPath
from fhirpath.fql.types import Term
from fhirpath.fql.types import TermValue
from fhirpath.interfaces import IQuery
from fhirpath.interfaces import IQueryResult
from fhirpath.interfaces.fql import IExistsTerm
from fhirpath.interfaces.fql import IGroupTerm
from fhirpath.interfaces.fql import ITerm
from fhirpath.query import QueryBuilder
from fhirpath.storage import PATH_INFO_STORAGE
from fhirpath.utils import import_string
from fhirpath.utils import lookup_fhir_class_path


def test_term_normal(engine):
    """Sample pytest test function with the pytest fixture as an argument."""
    term = Term("Patient.active", "false")
    term.finalize(engine)

    assert term.value() is False
    assert term.arithmetic_operator == OPERATOR.and_

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

    assert term.comparison_operator == OPERATOR.ge
    assert isinstance(term.value(), datetime)


def test_expression_add(engine):
    """ """
    term = and_("Patient.name.given", "Krog")
    term.finalize(engine)
    assert ITerm.providedBy(term)
    assert term.arithmetic_operator == OPERATOR.and_
    assert term.path.context.multiple is True

    term = T_("Patient.name.period.start")
    term = and_(-term, datetime.now().isoformat(timespec="seconds"))
    term.finalize(engine)
    assert term.unary_operator == OPERATOR.neg

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
    assert term.arithmetic_operator == OPERATOR.or_
    assert term.path.context.parent.prop_name == "for_fhir"

    term = T_("Patient.name.period.start")

    term = or_(-term, datetime.now().isoformat(timespec="seconds"))
    term.finalize(engine)
    assert term.unary_operator == OPERATOR.neg

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
    assert term.unary_operator == OPERATOR.pos

    # test not exists
    term = not_exists_("Task.for.reference")
    term.finalize(engine)
    assert term.unary_operator == OPERATOR.neg

    # Test from Term
    term = T_("Task.for.reference")
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

    assert term.unary_operator == OPERATOR.neg
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

    assert term.unary_operator == OPERATOR.neg


def test_sa_expression(engine):
    """ """
    term = T_("Organization.id")
    value = V_("f0")
    term = sa_(term, value)
    term.finalize(engine)

    assert term.comparison_operator == OPERATOR.sa


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


def test_type_path_element(engine):
    """ """
    path_ = ElementPath("Patient.name")
    path_.finalize(engine)
    path_ = path_ / "firstname"

    assert path_.path == "Patient.name.firstname"


def test_type_path_constraint():
    """where(type='successor').​resource
            where(resolve() is Patient)
            where(system='email')
            where(type='predecessor').​resource
            """
    path_ = ElementPath("Patient.telecom.where(system='email')")
    assert path_._where is not None
    assert path_._where.value == "email"
    assert path_._where.name == "system"
    assert path_._where.subpath is None
    assert path_._where.type == WhereConstraintType.T1

    path_ = ElementPath("CarePlan.subject.where(resolve() is Patient)")
    assert path_._where.value == "Patient"
    assert path_._where.name is None
    assert path_._where.subpath is None
    assert path_._where.type == WhereConstraintType.T2

    path_ = ElementPath(
        "ActivityDefinition.relatedArtifact.where(type='composed-of').resource"
    )
    assert path_._where.value == "composed-of"
    assert path_._where.name is None
    assert path_._where.subpath == "resource"
    assert path_._where.type == WhereConstraintType.T3


def test_path_constraint_as():
    """Condition.​abatement.​as(Range)
    Condition.​abatement.​as(dateTime)
    Condition.​abatement.​as(Period)
    """
    path_ = ElementPath("Condition.abatement.as(Range)")
    assert path_._path == "Condition.abatementRange"
    path_ = ElementPath("Condition.abatement.as(dateTime)")
    assert path_._path == "Condition.abatementDateTime"


def test_path_constraint_as_complex():
    """ """
    path_ = ElementPath("MedicationRequest.medication as CodeableConcept")
    assert path_._path == "MedicationRequest.medicationCodeableConcept"


def test_path_constains_index():
    """ """
    path_ = ElementPath("Organization.address[0].line[1]")
    assert path_._path == "Organization.address"


def test_path_constains_function():
    """ """
    path_ = ElementPath("Organization.address.first()")
    assert path_._path == "Organization.address"

    path_ = ElementPath("Organization.telecom.Take(1)")
    assert path_._path == "Organization.telecom"

    path_ = ElementPath("Organization.telecom.Skip(0)")
    assert path_._path == "Organization.telecom"
