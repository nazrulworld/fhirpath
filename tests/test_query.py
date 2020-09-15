# _*_ coding: utf-8 _*_
import pytest

from fhirpath import Q_
from fhirpath.engine import EngineResultRow
from fhirpath.enums import SortOrderType
from fhirpath.exceptions import MultipleResultsFound
from fhirpath.exceptions import ValidationError
from fhirpath.fql import T_
from fhirpath.fql import V_
from fhirpath.fql import ElementPath
from fhirpath.fql import exists_
from fhirpath.fql import in_
from fhirpath.fql import not_
from fhirpath.fql import not_in_
from fhirpath.fql import sort_

from ._utils import load_organizations_data


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def test_fetch_all(es_data, engine):
    """ """
    conn, meta_info = es_data
    load_organizations_data(conn, 152)

    builder = Q_(resource="Organization", engine=engine)
    builder = (
        builder.where(T_("Organization.active") == V_("true"))
        .where(T_("Organization.meta.lastUpdated", "2010-05-28T05:35:56+00:00"))
        .sort(sort_("Organization.meta.lastUpdated", SortOrderType.DESC))
        .limit(20, 2)
    )

    for resource in builder(async_result=False):
        assert resource.__class__.__name__ == "Organization"
        # test fetch all
    result = builder(async_result=False).fetchall()
    assert result.__class__.__name__ == "EngineResult"


def test_exists_query(es_data, engine):
    """ enteredDate"""
    builder = Q_(resource="ChargeItem", engine=engine)
    builder = builder.where(exists_("ChargeItem.enteredDate"))

    result = builder(async_result=False).fetchall()
    assert result.header.total == 1


def test_single_query(es_data, engine):
    """ """
    builder = Q_(resource="ChargeItem", engine=engine)
    builder = builder.where(exists_("ChargeItem.enteredDate"))

    result = builder(async_result=False).single()
    assert result is not None
    assert isinstance(result, EngineResultRow)
    # test empty result
    builder = Q_(resource="ChargeItem", engine=engine)
    builder = builder.where(not_(exists_("ChargeItem.enteredDate")))

    result = builder(async_result=False).single()
    assert result is None

    # Test Multiple Result error
    conn, meta_info = es_data
    load_organizations_data(conn, 2)

    builder = Q_(resource="Organization", engine=engine)
    builder = builder.where(T_("Organization.active", "true"))

    with pytest.raises(MultipleResultsFound) as excinfo:
        builder(async_result=False).single()
    assert excinfo.type == MultipleResultsFound


def test_first_query(es_data, engine):
    """ """
    conn, meta_info = es_data
    load_organizations_data(conn, 5)

    builder = Q_(resource="Organization", engine=engine)
    builder = builder.where(T_("Organization.active", "true"))

    result = builder(async_result=False).first()
    assert isinstance(result, EngineResultRow)

    builder = Q_(resource="Organization", engine=engine)
    builder = builder.where(T_("Organization.active", "false"))

    result = builder(async_result=False).first()
    assert result is None


def test_in_query(es_data, engine):
    """ """
    builder = Q_(resource="Organization", engine=engine)
    builder = builder.where(T_("Organization.active") == V_("true")).where(
        in_(
            "Organization.meta.lastUpdated",
            (
                "2010-05-28T05:35:56+00:00",
                "2001-05-28T05:35:56+00:00",
                "2018-05-28T05:35:56+00:00",
            ),
        )
    )
    result = builder(async_result=False).fetchall()
    assert result.header.total == 1

    # Test NOT IN
    builder = Q_(resource="Organization", engine=engine)
    builder = builder.where(T_("Organization.active") == V_("true")).where(
        not_in_(
            "Organization.meta.lastUpdated",
            (
                "2010-05-28T05:35:56+00:00",
                "2001-05-28T05:35:56+00:00",
                "2018-05-28T05:35:56+00:00",
            ),
        )
    )
    result = builder(async_result=False).fetchall()
    assert result.header.total == 0


def test_select_muiltipaths(es_data, engine):
    """ """
    builder = Q_(resource="Organization", engine=engine).select(
        "Organization.name", "Organization.address"
    )
    builder = builder.where(T_("Organization.active") == V_("true"))
    result = builder(async_result=False).fetchall()

    # FIXME looks like we changed how things are built here
    assert len(result.body[0]) == 2


def test_result_count(es_data, engine):
    """ """
    conn, meta_info = es_data
    load_organizations_data(conn, 5)
    builder = Q_(resource="Organization", engine=engine)
    builder = builder.where(T_("Organization.active") == V_("true"))
    total = builder(async_result=False).count()

    assert total == 6


def test_result_empty(es_data, engine):
    """ """
    conn, meta_info = es_data
    load_organizations_data(conn, 5)
    builder = Q_(resource="Organization", engine=engine)
    builder = builder.where(T_("Organization.active") == V_("false"))
    empty = builder(async_result=False).empty()
    assert empty is True


def test_result_with_path_contains_index(es_data, engine):
    """ """
    conn, meta_info = es_data
    load_organizations_data(conn, 5)
    builder = Q_(resource="Organization", engine=engine)
    builder = builder.select(
        "Organization.name.count()", "Organization.address[1]"
    ).where(T_("Organization.active") == V_("true"))
    result = builder(async_result=False).fetchall()
    expected_length = "Burgers University Medical Center"
    expected_postal_code = "9100 AA"

    assert result.body[0][0] == len(expected_length)
    assert result.body[0][1]["postalCode"] == expected_postal_code


def test_result_path_contains_function(es_data, engine):
    """ """
    builder = Q_(resource="Patient", engine=engine)
    builder = builder.select(
        "Patient.name.first().given.Skip(0).Take(0)",
        "Patient.identifier.last().assigner.display",
    ).where(T_("Patient.gender") == V_("male"))
    result = builder(async_result=False).fetchall()

    assert result.body[0][0] == "Patient"
    assert result.body[0][1] == "Zitelab ApS"

    # Test Some exception
    with pytest.raises(NotImplementedError):
        builder = Q_(resource="Patient", engine=engine)
        builder = builder.select("Patient.language.Skip(0)").where(
            T_("Patient.gender") == V_("male")
        )
        result = builder(async_result=False).first()

    with pytest.raises(ValidationError):
        builder = Q_(resource="Patient", engine=engine)
        builder = builder.select("Patient.address[0].Skip(0)").where(
            T_("Patient.gender") == V_("male")
        )
        result = builder(async_result=False).first()


def test_query_with_non_fhir_select(es_data, engine):
    """ """
    builder = Q_(resource="Patient", engine=engine)
    el_path1 = ElementPath("creation_date", non_fhir=True)
    el_path2 = ElementPath("title", non_fhir=True)
    builder = builder.select(el_path1, el_path2).where(
        T_("Patient.gender") == V_("male")
    )

    result = builder(async_result=False).fetchall()

    assert len(result.header.selects) == 2
    assert "creation_date" in result.header.selects
