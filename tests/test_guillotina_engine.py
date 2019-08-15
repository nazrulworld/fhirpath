# _*_ coding: utf-8 _*_
from guillotina.component import query_utility
from guillotina_elasticsearch.tests.utils import setup_txn_on_container

from fhirpath.enums import FHIR_VERSION
from fhirpath.fql import Q_
from fhirpath.fql import T_
from fhirpath.providers.guillotina_app.engine import EsEngine
from fhirpath.providers.guillotina_app.interfaces import IElasticsearchEngineFactory

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
        await load_organizations_data(requester, 161)
        engine = query_utility(IElasticsearchEngineFactory).get()

        index_name = await engine.get_index_name(container)

        conn = engine.connection.raw_connection()
        await conn.indices.refresh(index=index_name)

        query = Q_(resource="Organization", engine=engine)

        result_query = query.where(T_("Organization.active") == "true")(
            async_result=True
        )
        # Test scrol api! although default size is 100 but engine should collect all
        # by chunking based
        result = await result_query._engine.execute(
            result_query._query, result_query._unrestricted
        )
        assert result.header.total == len(result.body)

        # Test limit works
        result_query = query.where(T_("Organization.active") == "true").limit(20)(
            async_result=True
        )
        result = await result_query._engine.execute(
            result_query._query, result_query._unrestricted
        )

        assert 20 == len(result.body)
        # Test with bundle wrapper
        bundle = engine.wrapped_with_bundle(result)

        assert bundle.total == result.header.total
