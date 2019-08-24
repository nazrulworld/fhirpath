# _*_ coding: utf-8 _*_
from guillotina.component import query_utility
from guillotina_elasticsearch.tests.utils import setup_txn_on_container

from fhirpath.enums import SortOrderType
from fhirpath.fql import Q_
from fhirpath.fql import T_
from fhirpath.fql import V_
from fhirpath.fql import sort_
from fhirpath.providers.guillotina_app.interfaces import IElasticsearchEngineFactory

from .fixtures import init_data
from .fixtures import load_organizations_data


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
