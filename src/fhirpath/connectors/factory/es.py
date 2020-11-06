# _*_ coding: utf-8 _*_
import inspect
import logging

from elasticsearch.exceptions import SerializationError
from pydantic.json import pydantic_encoder
from zope.interface import Invalid

from fhirpath.enums import EngineQueryType
from fhirpath.json import json_dumps, json_loads
from fhirpath.utils import import_string

from ..connection import Connection
from ..url import _parse_rfc1738_args
from . import ConnectionFactory

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.providers.plone.engine")


class ElasticsearchJSONSerializer:
    """Custom serializer, supports orjson, simplejson,
    with correct default encoder which fit for FHIR Resources"""

    mimetype = "application/json"

    def default(self, data):
        return pydantic_encoder(data)

    def loads(self, s):
        try:
            return json_loads(s)
        except (ValueError, TypeError) as e:
            raise SerializationError(s, e)

    def dumps(self, data):
        # don't serialize strings
        if isinstance(data, (str, bytes)):
            return data
        try:
            return json_dumps(data, return_bytes=False)
        except (ValueError, TypeError) as e:
            raise SerializationError(data, e)


class EsConnMixin:
    def evaluate_result(self, result):
        """ """
        if result.get("_shards", {}).get("failed", 0) > 0:
            logger.warning(f'Error running query: {result["_shards"]}')
            error_message = "Unknown"
            for failure in result["_shards"].get("failures") or []:
                error_message = failure["reason"]
            raise Invalid(error_message)

    def finalize_search_params(self, compiled_query, query_type=EngineQueryType.DML):
        """ """
        compiled_query = compiled_query.copy()
        params = dict()

        from_ = compiled_query.pop("from", 0)
        size = compiled_query.pop("size", 100)
        scroll = compiled_query.pop("scroll", None)
        ignore_unavailable = compiled_query.pop("ignore_unavailable", True)

        if query_type == EngineQueryType.DML:
            params["from_"] = from_
            params["size"] = size
            if scroll is not None:
                params["scroll"] = scroll
        elif query_type == EngineQueryType.COUNT:
            compiled_query.pop("_source", None)

        params["ignore_unavailable"] = ignore_unavailable
        params["body"] = compiled_query
        return params


class ElasticsearchConnection(Connection, EsConnMixin):
    """Elasticsearch Connection"""

    @classmethod
    def from_url(cls, url: str):
        """ """
        if isinstance(url, (list, tuple)):
            url = [_parse_rfc1738_args(u) for u in url]
        else:
            url = _parse_rfc1738_args(url)

        self = create(url, "elasticsearch.Elasticsearch", wrapper_class=cls)
        return self

    @staticmethod
    def real_index(index):
        """ """
        if isinstance(index, str):
            return index
        if inspect.isfunction(index) or inspect.ismethod(index):
            return index()
        raise NotImplementedError

    def server_info(self):
        """ """
        info = {}
        try:
            conn = self.raw_connection
            info = conn.info()
        except Exception as exc:
            logger.warning(
                "Could not retrieve Elasticsearch Server info, "
                f"there is problem with connection. {exc}"
            )
        return info

    def fetch(self, index, compiled_query):
        """xxx: must have use scroll+slice
        https://stackoverflow.com/questions/43211387/
        what-does-elasticsearch-automatic-slicing-do
        https://stackoverflow.com/questions/50376713/
        elasticsearch-scroll-api-with-multi-threading
        """
        search_params = self.finalize_search_params(compiled_query, EngineQueryType.DML)
        conn = self.raw_connection
        result = conn.search(
            index=ElasticsearchConnection.real_index(index), **search_params
        )
        self.evaluate_result(result)
        return result

    def count(self, index, compiled_query):
        """ """
        search_params = self.finalize_search_params(
            compiled_query, EngineQueryType.COUNT
        )
        conn = self.raw_connection
        result = conn.count(
            index=ElasticsearchConnection.real_index(index), **search_params
        )
        self.evaluate_result(result)
        return result

    def scroll(self, scroll_id, scroll="30s"):
        """ """
        result = self.raw_connection.scroll(
            body={"scroll_id": scroll_id}, scroll=scroll
        )
        self.evaluate_result(result)
        return result


class AsyncElasticsearchConnection(Connection, EsConnMixin):
    """Elasticsearch Connection"""

    @classmethod
    def is_async(cls):
        return True

    @classmethod
    def from_url(cls, url: str):
        """ """
        if isinstance(url, (list, tuple)):
            url = [_parse_rfc1738_args(u) for u in url]
        else:
            url = _parse_rfc1738_args(url)

        self = create(url, "elasticsearch.AsyncElasticsearch", wrapper_class=cls)
        return self

    async def server_info(self):
        """ """
        info = {}
        try:
            conn = self.raw_connection
            info = await conn.info()
        except Exception as exc:
            logger.warning(
                "Could not retrieve Elasticsearch Server info, "
                f"there is problem with connection. {exc}"
            )
        return info

    @staticmethod
    async def real_index(index):
        """ """
        if isinstance(index, str):
            return index
        if inspect.iscoroutine(index):
            return await index()
        if inspect.isawaitable(index):
            return await index
        if inspect.isfunction(index) or inspect.ismethod(index):
            return index()
        raise NotImplementedError

    async def fetch(self, index, compiled_query):
        """xxx: must have use scroll+slice
        https://stackoverflow.com/questions/43211387/
        what-does-elasticsearch-automatic-slicing-do
        https://stackoverflow.com/questions/50376713/
        elasticsearch-scroll-api-with-multi-threading
        """
        search_params = self.finalize_search_params(compiled_query, EngineQueryType.DML)
        conn = self.raw_connection
        result = await conn.search(
            index=await AsyncElasticsearchConnection.real_index(index), **search_params
        )
        self.evaluate_result(result)
        return result

    async def count(self, index, compiled_query):
        """ """
        search_params = self.finalize_search_params(
            compiled_query, EngineQueryType.COUNT
        )
        conn = self.raw_connection
        result = await conn.count(
            index=await AsyncElasticsearchConnection.real_index(index), **search_params
        )
        self.evaluate_result(result)
        return result

    async def scroll(self, scroll_id, scroll="30s"):
        """ """
        result = await self.raw_connection.scroll(
            body={"scroll_id": scroll_id}, scroll=scroll
        )
        self.evaluate_result(result)
        return result


class ElasticsearchConnectionFactory(ConnectionFactory):
    """ """

    def wrap(self, raw_conn):
        """ """
        if isinstance(self.url, (list, tuple)):
            url_ = self.url[0]
        else:
            url_ = self.url

        wrapper_class = url_.query.get("wrapper_class", self.wrapper_class)
        if wrapper_class is None:
            if raw_conn.__class__.__name__ == "AsyncElasticsearch":
                wrapper_class = AsyncElasticsearchConnection
            else:
                wrapper_class = ElasticsearchConnection

        if isinstance(wrapper_class, (str, bytes)):
            wrapper_class = import_string(wrapper_class)

        return wrapper_class.from_prepared(raw_conn)

    def prepare_params(self):
        """params for elasticsearch """
        if not isinstance(self.url, (list, tuple)):
            urls = [self.url]
        else:
            urls = self.url

        params = {"hosts": list()}
        params.update(self.extra)

        def _make_bool(string):
            return string.lower() in (
                "true",
                "t",
                "yes",
                "y",
                "1",
            )

        for url in urls:
            item = {"host": url.host, "port": url.port or 9200}
            query = url.query.copy()
            if url.username:
                item["http_auth"] = "{0}:{1}".format(url.username, url.password or "")
            if "use_ssl" in query:
                item["use_ssl"] = _make_bool(query.pop("use_ssl"))
            if "url_prefix" in query:
                item["url_prefix"] = query.pop("url_prefix")
            params["hosts"].append(item)

            if "sniff_on_start" in query:
                params["sniff_on_start"] = _make_bool(query.pop("sniff_on_start"))
            if "sniffer_timeout" in query:
                params["sniffer_timeout"] = int(query.pop("sniffer_timeout"))
            if "sniff_timeout" in query:
                params["sniff_timeout"] = float(query.pop("sniff_timeout"))
            if "sniff_on_connection_fail" in query:
                params["sniff_on_connection_fail"] = _make_bool(
                    query.pop("sniff_on_connection_fail")
                )
            if "max_retries" in query:
                params["max_retries"] = int(query.pop("max_retries"))
            if "retry_on_status" in query:
                params["retry_on_status"] = tuple(
                    map(
                        lambda x: int(x.strip()),
                        query.pop("retry_on_status").split(","),
                    )
                )
            if "retry_on_timeout" in query:
                params["retry_on_timeout"] = _make_bool(query.pop("retry_on_timeout"))
            if "serializer" in query:
                params["serializer"] = import_string(query.pop("serializer"))()
            if "host_info_callback" in query:
                params["host_info_callback"] = import_string(
                    query.pop("host_info_callback")
                )

        return params

    def __call__(self):
        """ """
        params = self.prepare_params()
        raw_conn = self.klass(**params)

        return self.wrap(raw_conn)


def create(url, conn_class=None, **extra):
    """
    :param url: instance of URL or list of URL.

    :param conn_class: The Connection class.
    """
    use_es_serializer = extra.pop("use_es_serializer", False)
    if "serializer" not in extra and use_es_serializer is False:
        extra["serializer"] = ElasticsearchJSONSerializer()

    if conn_class is None:
        conn_class = "elasticsearch.Elasticsearch"

    factory = ElasticsearchConnectionFactory(url, klass=conn_class, **extra)
    return factory()
