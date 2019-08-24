# _*_ coding: utf-8 _*_
import logging

from DateTime import DateTime
from yarl import URL
from zope.component import getUtility
from zope.globalrequest import getRequest
from zope.interface import Invalid
from zope.schema import getFields

from collective.elasticsearch.interfaces import IElasticSearchCatalog
from fhirpath.connectors import create_connection
from fhirpath.engine import Connection
from fhirpath.types import FhirDateTime
from plone import api
from plone.behavior.interfaces import IBehavior
from Products.CMFCore.permissions import AccessInactivePortalContent
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.utils import _getAuthenticatedUser
from fhirpath.engine.es import ElasticsearchEngine as BaseEngine


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.providers.plone.engine")


class ElasticsearchConnection(Connection):
    """Elasticsearch Connection"""

    @classmethod
    def from_url(cls, url: str):
        """ """
        self = cls(create_connection(url, "elasticsearch.Elasticsearch"))
        return self

    def server_info(self):
        """ """
        try:
            conn = self.raw_connection()
            info = conn.info()
        except Exception:
            logger.warning(
                "Could not retrieve Elasticsearch Server info, "
                "there is problem with connection."
            )
        return info

    def finalize_search_params(self, compiled_query):
        """ """
        compiled_query = compiled_query.copy()
        params = dict()
        params["from_"] = compiled_query.pop("from", 0)
        params["size"] = compiled_query.pop("size", 100)
        if "scroll" in compiled_query:
            params["scroll"] = compiled_query.pop("scroll")
        params["ignore_unavailable"] = compiled_query.pop("ignore_unavailable", True)
        params["body"] = compiled_query
        return params

    def fetch(self, compiled_query):
        """xxx: must have use scroll+slice
        https://stackoverflow.com/questions/43211387/what-does-elasticsearch-automatic-slicing-do
        https://stackoverflow.com/questions/50376713/elasticsearch-scroll-api-with-multi-threading
        """
        search_params = self.finalize_search_params(compiled_query)
        conn = self.raw_connection()
        result = conn.search(**search_params)
        self._evaluate_result(result)
        return result

    def _evaluate_result(self, result):
        """ """
        if result.get("_shards", {}).get("failed", 0) > 0:
            logger.warning(f'Error running query: {result["_shards"]}')
            error_message = "Unknown"
            for failure in result["_shards"].get("failures") or []:
                error_message = failure["reason"]
            raise Invalid(reason=error_message)

    def scroll(self, scroll_id, scroll="30s"):
        """ """
        result = self.raw_connection().scroll(
            body={"scroll_id": scroll_id}, scroll=scroll
        )
        self._evaluate_result(result)
        return result


class ElasticsearchEngine(BaseEngine):
    """Elasticsearch Engine"""

    def __init__(self, es_catalog, fhir_release, conn_factory, dialect_factory):
        """ """
        self.es_catalog = IElasticSearchCatalog(es_catalog)
        super(ElasticsearchEngine, self).__init__(
            fhir_release, conn_factory, dialect_factory
        )

    def get_index_name(self):
        """ """
        self.es_catalog.index_name

    def build_security_query(self):
        # The users who has plone.AccessContent permission by prinperm
        # The roles who has plone.AccessContent permission by roleperm
        show_inactive = False  # we will take care later
        user = _getAuthenticatedUser(self.es_catalog.catalogtool)
        users_roles = self.es_catalog.catalogtool._listAllowedRolesAndUsers(user)
        params = {"allowedRolesAndUsers": users_roles}
        if not show_inactive and not _checkPermission(
            AccessInactivePortalContent, self.es_catalog.catalogtool
        ):
            params["effectiveRange"] = FhirDateTime(DateTime().ISO8601())

        return params

    def calculate_field_index_name(self, resource_type):
        """1.) xxx: should be cached

        """
        # Products.CMFPlone.TypesTool.TypesTool
        types_tool = api.portal.get_tool("portal_types")
        factory = types_tool.getTypeInfo(resource_type)
        name = None

        if factory:
            name = ElasticsearchEngine.field_index_name_from_factory(
                factory, resource_type=resource_type
            )

        if name is None:
            for type_name in types_tool.listContentTypes():
                factory = types_tool.getTypeInfo(type_name)
                if factory.meta_type != "Dexterity FTI":
                    continue
                name = ElasticsearchEngine.field_index_name_from_factory(
                    factory, resource_type=resource_type
                )
                if name:
                    break

        if name and name in self.es_catalog.catalogtool.indexes():
            return name

    @staticmethod
    def field_index_name_from_factory(factory, resource_type=None):
        """ """
        if resource_type is None:
            resource_type = factory.id

        def _from_schema(schema):
            for name, field in getFields(schema).items():
                if (
                    field.__class__.__name__ == "FhirResource"
                    and resource_type == field.get_resource_type()
                ):
                    return name

        schema = factory.lookupSchema() or factory.lookupModel().schema
        name = _from_schema(schema)
        if name:
            return name

        for behavior in factory.behaviors:
            schema = getUtility(IBehavior, name=behavior).interface
            if schema is None:
                continue
            name = _from_schema(schema)
            if name:
                return name

    def current_url(self):
        """
        complete url from current request
        return yarl.URL"""
        request = getRequest()
        if request is None:
            # fallback
            request = api.portal.get().REQUEST
        base_url = URL(request.getURL())

        if request.get("QUERY_STRING", None):
            url = base_url.with_query(request.get("QUERY_STRING", None))
        else:
            url = base_url
        return url

    def extract_hits(self, fieldname, hits, container):
        """ """
        for res in hits:
            if res["_type"] != "portal_catalog":
                continue
            if fieldname in res["_source"]:
                container.append(res["_source"][fieldname])
