# _*_ coding: utf-8 _*_
from guillotina.component import query_utility
from guillotina_elasticsearch.tests.utils import setup_txn_on_container

from fhirpath.enums import FHIR_VERSION
from fhirpath.interfaces import ISearchContextFactory
from fhirpath.providers.guillotina_app.interfaces import IElasticsearchEngineFactory
from fhirpath.providers.guillotina_app.engine import EsEngine
from fhirpath.providers.guillotina_app.interfaces import IFhirSearch
from fhirpath.fql import T_
from fhirpath.fql import Q_

from .fixtures import init_data
from .fixtures import load_organizations_data


__author__ = "Md Nazrul Islam<nazrul@zitelab.dk>"


def test_engine_calculate_field_index_name(dummy_guillotina):
    """ """
    engine = EsEngine(FHIR_VERSION.DEFAULT, lambda x: "Y", lambda x: "Y")
    name = engine.calculate_field_index_name("Organization")

    assert name == "organization_resource"

    name = engine.calculate_field_index_name("NonRegisteredContentType")
    assert name is None


async def test_raw_result(es_requester):
    """ """
    async with es_requester as requester:
        container, request, txn, tm = await setup_txn_on_container(requester)  # noqa
        # init primary data
        await init_data(requester)
        await load_organizations_data(requester, 59)
        engine = query_utility(IElasticsearchEngineFactory).get()

        index_name = await engine.get_index_name(container)

        conn = engine.connection.raw_connection()
        await conn.indices.refresh(index=index_name)

        query = Q_(resource="Organization", engine=engine)

        result_query = query.where(T_("Organization.active") == "true").limit(20)(
            async_result=True
        )

        result = await result_query.fetchall()
        import pytest

        pytest.set_trace()
        pass
