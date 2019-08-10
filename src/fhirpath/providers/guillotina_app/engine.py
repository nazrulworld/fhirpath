# _*_ coding: utf-8 _*_
import logging

from guillotina.component import get_adapter
from guillotina.component import get_utilities_for
from guillotina.component import query_utility
from guillotina.directives import index_field
from guillotina.interfaces import IResourceFactory
from guillotina.utils import get_current_container
from guillotina_elasticsearch.interfaces import IIndexManager

from fhirpath.engine import Connection
from fhirpath.engine import Engine


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.providers.guillotina.engine")


class EsConnection(Connection):
    """Elasticsearch Connection"""

    async def server_info(self):
        info = {}
        try:
            conn = self.raw_connection()
            info = await conn.info()
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
        params["ignore_unavailable"] = compiled_query.pop("ignore_unavailable", True)
        params["body"] = compiled_query
        return params


class EsEngine(Engine):
    """Elasticsearch Engine"""

    async def get_index_name(self, container=None):
        """ """
        if container is None:
            container = get_current_container()

        index_manager = get_adapter(container, IIndexManager)

        return await index_manager.get_index_name()

    async def execute(self, query):
        """ """
        compiled = self.dialect.compile(query)
        compiled
        pass

    def calculate_field_index_name(self, resource_types):
        """1.) xxx: should be cached
        """
        factory = query_utility(IResourceFactory, name=resource_types)
        if factory:
            name = EsEngine.field_index_name_from_factory(
                factory, resource_type=resource_types
            )
            if name:
                return name

        types = [x[1] for x in get_utilities_for(IResourceFactory)]
        for factory in types:
            name = EsEngine.field_index_name_from_factory(
                factory, resource_type=resource_types
            )
            if name:
                return name

    @staticmethod
    def field_index_name_from_factory(factory, resource_type=None):
        """ """
        if resource_type is None:
            resource_type = factory.type_name

        def _find(schema):
            field_indexes = schema.queryTaggedValue(index_field.key, default={})
            for name in field_indexes:
                configs = field_indexes[name]
                if (
                    "fhirpath_enabled" in configs
                    and configs["fhirpath_enabled"] is True
                ):
                    if resource_type == configs["resource_type"]:
                        return name
            return None

        name = _find(factory.schema)
        if name is not None:
            return name

        for behavior in factory.behaviors:
            tagged_query = getattr(behavior, "queryTaggedValue", None)
            if tagged_query is None:
                continue
            name = _find(behavior)
            if name is not None:
                return name
