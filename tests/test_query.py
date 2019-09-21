# _*_ coding: utf-8 _*_
import pytest

from fhirpath.enums import SortOrderType
from fhirpath.exceptions import MultipleResultsFound
from fhirpath.fhirpath import Q_
from fhirpath.fql import T_
from fhirpath.fql import V_
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
        assert resource.__class__.__name__ == "OrganizationModel"
        # test fetch all
    result = builder(async_result=False).fetchall()
    result.__class__.__name__ == "EngineResult"


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
    assert isinstance(result, builder._from[0][1])
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
    assert isinstance(result, builder._from[0][1])

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
