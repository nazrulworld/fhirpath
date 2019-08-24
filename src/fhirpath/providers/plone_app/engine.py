# _*_ coding: utf-8 _*_
import logging

from DateTime import DateTime
from yarl import URL
from zope.component import getUtility
from zope.globalrequest import getRequest
from zope.schema import getFields

from collective.elasticsearch.interfaces import IElasticSearchCatalog
from fhirpath.engine.es import ElasticsearchEngine as BaseEngine
from fhirpath.types import FhirDateTime
from plone import api
from plone.behavior.interfaces import IBehavior
from Products.CMFCore.permissions import AccessInactivePortalContent
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.utils import _getAuthenticatedUser


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.providers.plone.engine")


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
