# _*_ coding: utf-8 _*_
import logging
from plone import api
from collective.elasticsearch.interfaces import IElasticSearchCatalog
from fhirpath.engine import Connection
from fhirpath.engine import Engine
from fhirpath.engine import EngineResult
from fhirpath.engine import EngineResultBody
from fhirpath.engine import EngineResultHeader
from fhirpath.utils import BundleWrapper
from fhirpath.utils import import_string
from zope.interface import Invalid
from zope.schema import getFields
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.utils import _getAuthenticatedUser
from Products.CMFCore.permissions import AccessInactivePortalContent
from DateTime import DateTime
from fhirpath.types import FhirDateTime


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.providers.plone.engine")


class ElasticsearchConnection(Connection):
    """Elasticsearch Connection"""

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


class ElasticsearchEngine(Engine):
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

    def execute(self, query, unrestricted=False):
        """ """
        # for now we support single from resource
        resource_type = query.get_from()[0][1].resource_type
        field_index_name = self.calculate_field_index_name(resource_type)

        params = {"query": query, "root_replacer": field_index_name}
        if unrestricted is False:
            params["security_callable"] = self.build_security_query

        compiled = self.dialect.compile(**params)
        raw_result = self.connection.fetch(compiled)

        # xxx: process result
        result = self.process_raw_result(raw_result, field_index_name)
        result.header.raw_query = self.connection.finalize_search_params(compiled)

        return result

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
            name = ElasticsearchEngine.field_index_name_from_factory(factory)

        if name is None:
            for type_name in types_tool.listContentTypes():
                factory = types_tool.getTypeInfo(type_name)
                name = ElasticsearchEngine.field_index_name_from_factory(factory)
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
            schema = import_string(behavior)
            name = _from_schema(schema)
            if name:
                return name

    def process_raw_result(self, rawresult, fieldname):
        """ """
        header = EngineResultHeader(total=rawresult["hits"]["total"]["value"])
        body = EngineResultBody()

        def extract(hits):
            for res in hits:
                if res["_type"] != "_doc":
                    continue
                if fieldname in res["_source"]:
                    body.append(res["_source"][fieldname])

        # extract primary data
        extract(rawresult["hits"]["hits"])

        if "_scroll_id" in rawresult and header.total > len(rawresult["hits"]["hits"]):
            # we need to fetch all!
            consumed = len(rawresult["hits"]["hits"])

            while header.total > consumed:
                # xxx: dont know yet, if from_, size is better solution
                raw_res = self.connection.scroll(rawresult["_scroll_id"])
                if len(raw_res["hits"]["hits"]) == 0:
                    break

                extract(raw_res["hits"]["hits"])

                consumed += len(raw_res["hits"]["hits"])

                if header.total <= consumed:
                    break

        return EngineResult(header=header, body=body)

    def wrapped_with_bundle(self, result):
        """ """
        request = get_current_request()
        url = request.rel_url
        wrapper = BundleWrapper(self, result, url, "searchset")
        return wrapper()
