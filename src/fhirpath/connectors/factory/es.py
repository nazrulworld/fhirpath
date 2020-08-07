# _*_ coding: utf-8 _*_
import logging

from zope.interface import Invalid

from fhirpath.enums import EngineQueryType
from fhirpath.utils import import_string

from ..connection import Connection
from ..url import _parse_rfc1738_args
from . import ConnectionFactory

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.providers.plone.engine")


class ElasticsearchConnection(Connection):
    """Elasticsearch Connection"""

    @classmethod
    def from_url(cls, url: str):
        """ """
        if isinstance(url, (list, tuple)):
            url = [_parse_rfc1738_args(u) for u in url]
        else:
            url = _parse_rfc1738_args(url)

        self = cls(create(url, "elasticsearch.Elasticsearch"))
        return self

    def server_info(self):
        """ """
        try:
            conn = self.raw_connection
            info = conn.info()
        except Exception:
            logger.warning(
                "Could not retrieve Elasticsearch Server info, "
                "there is problem with connection."
            )
        return info

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

    def fetch(self, index, compiled_query):
        """xxx: must have use scroll+slice
        https://stackoverflow.com/questions/43211387/
        what-does-elasticsearch-automatic-slicing-do
        https://stackoverflow.com/questions/50376713/
        elasticsearch-scroll-api-with-multi-threading
        """
        search_params = self.finalize_search_params(compiled_query, EngineQueryType.DML)
        conn = self.raw_connection
        result = conn.search(index=index, **search_params)
        self._evaluate_result(result)
        return result

    def count(self, index, compiled_query):
        """ """
        search_params = self.finalize_search_params(
            compiled_query, EngineQueryType.COUNT
        )
        conn = self.raw_connection
        result = conn.count(index=index, **search_params)
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
        result = self.raw_connection.scroll(
            body={"scroll_id": scroll_id}, scroll=scroll
        )
        self._evaluate_result(result)
        return result


class ElasticsearchConnectionFactory(ConnectionFactory):
    """ """

    def wrap(self, raw_conn):
        """ """
        if isinstance(self.url, (list, tuple)):
            url_ = self.url[0]
        else:
            url_ = self.url

        wrapper_class = url_.query.get("wrapper_class", ElasticsearchConnection)

        if isinstance(wrapper_class, (str, bytes)):
            wrapper_class = import_string(wrapper_class)

        return wrapper_class.from_prepared(raw_conn)

    def prepare_params(self):
        """ """
        if not isinstance(self.url, (list, tuple)):
            urls = [self.url]
        else:
            urls = self.url

        host_info = list()

        for url in urls:
            item = {"host": url.host, "port": url.port or 9200}
            if url.username:
                item["http_auth"] = "{0}:{1}".format(url.username, url.password or "")
            if "use_ssl" in url.query:
                item["use_ssl"] = url.query.get("use_ssl").lower() in (
                    "true",
                    "t",
                    "yes",
                    "y",
                    "1",
                )
            if "url_prefix" in url.query:
                item["url_prefix"] = url.query.get("url_prefix")
            host_info.append(item)

        return {"hosts": host_info}

    def __call__(self):
        """ """
        params = self.prepare_params()
        raw_conn = self.klass(**params)

        return self.wrap(raw_conn)


def create(url, conn_class=None):
    """
    :param url: instance of URL or list of URL.

    :param conn_class: The Connection class.
    """
    if conn_class is None:
        conn_class = "elasticsearch.Elasticsearch"

    factory = ElasticsearchConnectionFactory(url, klass=conn_class)
    return factory()
