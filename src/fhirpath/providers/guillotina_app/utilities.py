# _*_ coding: utf-8 _*_
from copy import deepcopy

from guillotina import app_settings
from guillotina import configure
from guillotina.component import get_utility
from guillotina_elasticsearch.interfaces import IElasticSearchUtility

from fhirpath.dialects.elasticsearch import ElasticSearchDialect
from fhirpath.enums import FHIR_VERSION
from fhirpath.interfaces import ISearchContextFactory
from fhirpath.search import Search
from fhirpath.search import SearchContext

from .engine import EsConnection
from .engine import EsEngine
from .interfaces import IElasticsearchEngineFactory
from .interfaces import IFhirSearch


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def default_settings():

    settings = app_settings.get("fhirpath", dict()).get("default_settings", dict())
    return deepcopy(settings)


def create_engine(fhir_version=None):
    """ """
    if fhir_version is None:
        fhir_version = default_settings().get("fhir_version", None)

    if fhir_version is None:
        fhir_version = FHIR_VERSION.DEFAULT
    if isinstance(fhir_version, str):
        fhir_version = FHIR_VERSION[fhir_version]

    def es_conn_factory(engine):
        prepared_conn = get_utility(IElasticSearchUtility).get_connection()
        return EsConnection.from_prepared(prepared_conn)

    def es_dialect_factory(engine):
        """ """
        return ElasticSearchDialect(connection=engine.connection)

    engine_ = EsEngine(fhir_version, es_conn_factory, es_dialect_factory)

    return engine_


@configure.utility(provides=IElasticsearchEngineFactory)
class EsEngineFactory:
    """ """

    def get(fhir_version=None):
        """ """
        return create_engine(fhir_version)


@configure.utility(provides=ISearchContextFactory)
class SearchContextFactory:
    """ """

    def get(resource_type, fhir_version=None):
        """ """
        engine = create_engine(fhir_version)
        return SearchContext(engine, resource_type)


@configure.utility(provides=IFhirSearch)
class FhirSearch:
    """ """

    def __call__(self, params, context=None, resource_type=None, fhir_version=None):
        """ """
        if context is None:
            context = self.create_context(resource_type, fhir_version)

        search = Search.from_params(context, params)
        return search.build()

    def create_context(self, resource_type, fhir_version=None):
        """ """
        engine = create_engine(fhir_version)
        return SearchContext(engine, resource_type)
