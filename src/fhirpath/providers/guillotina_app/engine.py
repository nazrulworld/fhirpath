# _*_ coding: utf-8 _*_
import logging

from guillotina.component import get_adapter
from guillotina.component import get_utilities_for
from guillotina.component import query_utility
from guillotina.directives import index_field
from guillotina.interfaces import IResourceFactory
from guillotina.utils import get_authenticated_user
from guillotina.utils import get_current_container
from guillotina.utils import get_current_request
from guillotina.utils import get_security_policy
from guillotina_elasticsearch.exceptions import QueryErrorException
from guillotina_elasticsearch.interfaces import IIndexManager

from fhirpath.engine import Connection
from fhirpath.engine import Engine
from fhirpath.engine import EngineResult
from fhirpath.engine import EngineResultBody
from fhirpath.engine import EngineResultHeader
from fhirpath.utils import BundleWrapper


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
        if "scroll" in compiled_query:
            params["scroll"] = compiled_query.pop("scroll")
        params["ignore_unavailable"] = compiled_query.pop("ignore_unavailable", True)
        params["body"] = compiled_query
        return params

    async def fetch(self, compiled_query):
        """xxx: must have use scroll+slice
        https://stackoverflow.com/questions/43211387/what-does-elasticsearch-automatic-slicing-do
        https://stackoverflow.com/questions/50376713/elasticsearch-scroll-api-with-multi-threading
        """
        search_params = self.finalize_search_params(compiled_query)
        conn = self.raw_connection()
        result = await conn.search(**search_params)
        self._evaluate_result(result)
        return result

    def _evaluate_result(self, result):
        """ """
        if result.get("_shards", {}).get("failed", 0) > 0:
            logger.warning(f'Error running query: {result["_shards"]}')
            error_message = "Unknown"
            for failure in result["_shards"].get("failures") or []:
                error_message = failure["reason"]
            raise QueryErrorException(reason=error_message)

    async def scroll(self, scroll_id, scroll="30s"):
        """ """
        result = await self.raw_connection().scroll(
            body={"scroll_id": scroll_id}, scroll=scroll
        )
        self._evaluate_result(result)
        return result


class EsEngine(Engine):
    """Elasticsearch Engine"""

    async def get_index_name(self, container=None):
        """ """
        if container is None:
            container = get_current_container()

        index_manager = get_adapter(container, IIndexManager)

        return await index_manager.get_index_name()

    async def execute(self, query, unrestricted=False):
        """ """
        # for now we support single from resource
        resource_type = query.get_from()[0][1].resource_type
        field_index_name = self.calculate_field_index_name(resource_type)

        params = {"query": query, "root_replacer": field_index_name}
        if unrestricted is False:
            params["security_callable"] = self.build_security_query

        compiled = self.dialect.compile(**params)
        raw_result = await self.connection.fetch(compiled)

        # xxx: process result
        result = await self.process_raw_result(raw_result, field_index_name)
        result.header.raw_query = self.connection.finalize_search_params(compiled)

        return result

    def build_security_query(self):
        # The users who has plone.AccessContent permission by prinperm
        # The roles who has plone.AccessContent permission by roleperm
        users = []
        roles = []
        user = get_authenticated_user()
        policy = get_security_policy(user)

        users.append(user.id)
        users.extend(user.groups)

        roles_dict = policy.global_principal_roles(user.id, user.groups)
        roles.extend([key for key, value in roles_dict.items() if value])

        return {"access_roles": roles, "access_users": users}

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

    async def process_raw_result(self, rawresult, fieldname):
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
                raw_res = await self.connection.scroll(rawresult["_scroll_id"])
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
