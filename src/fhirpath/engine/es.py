# _*_ coding: utf-8 _*_
from zope.interface import implementer

from fhirpath.engine.base import Engine
from fhirpath.engine.base import EngineResult
from fhirpath.engine.base import EngineResultBody
from fhirpath.engine.base import EngineResultHeader
from fhirpath.interfaces import IElasticsearchEngine
from fhirpath.utils import BundleWrapper


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


@implementer(IElasticsearchEngine)
class ElasticsearchEngine(Engine):
    """Elasticsearch Engine"""

    def get_index_name(self):
        """ """
        raise NotImplementedError

    def get_mapping(self, resource_type):
        """ """
        raise NotImplementedError

    def _add_result_headers(self, query, result, source_filters, compiled):
        """ """
        # Process additional meta
        result.header.raw_query = self.connection.finalize_search_params(compiled)
        if len(source_filters) == 0:
            return

        resource_type = query.get_from()[0][0]
        selects = list()
        for path_ in source_filters:
            parts = path_.split(".")
            if len(parts) == 1:
                selects.append(resource_type)
            else:
                selects.append(".".join([resource_type] + parts[1:]))
        result.selects = selects

    def _get_source_filters(self, compiled):
        """ """
        source_filters = compiled.get("_source", {})
        if source_filters is False:
            return []
        else:
            return source_filters.get("includes", [])

    def _traverse_for_value(self, source, path_):
        """Looks path_ is innocent string key, but may content expression, function"""
        if isinstance(source, dict):
            # xxx: validate path, not blindly sending None
            return source.get(path_, None)
        else:
            # xxx: accept list type
            # xxx: accept path with index, function.
            raise NotImplementedError

    def _execute(self, query, unrestricted=False):
        """ """
        # for now we support single from resource
        query_copy = query.clone()
        resource_type = query.get_from()[0][1].resource_type
        field_index_name = self.calculate_field_index_name(resource_type)

        if unrestricted is False:
            self.build_security_query(query_copy)

        params = {
            "query": query_copy,
            "root_replacer": field_index_name,
            "mapping": self.get_mapping(resource_type),
        }

        compiled = self.dialect.compile(**params)
        raw_result = self.connection.fetch(compiled)

        return raw_result, field_index_name, compiled

    def execute(self, query, unrestricted=False):
        """ """
        raw_result, field_index_name, compiled = self._execute(query, unrestricted)

        source_filters = self._get_source_filters(compiled)

        # xxx: process result
        result = self.process_raw_result(raw_result, source_filters)

        # Process additional meta
        self._add_result_headers(query, result, source_filters, compiled)

        return result

    def build_security_query(self, query):
        """ """
        pass

    def calculate_field_index_name(self, resource_type):
        raise NotImplementedError

    def extract_hits(self, fieldname, hits, container):
        """ """
        raise NotImplementedError

    def process_raw_result(self, rawresult, selects):
        """ """
        # let´s make some compabilities
        if isinstance(rawresult["hits"]["total"], dict):
            total = rawresult["hits"]["total"]["value"]
        else:
            total = rawresult["hits"]["total"]

        result = EngineResult(
            header=EngineResultHeader(total=total), body=EngineResultBody()
        )
        if len(selects) == 0:
            # Nothing would be in body
            return result
        # extract primary data
        self.extract_hits(selects, rawresult["hits"]["hits"], result.body)

        if "_scroll_id" in rawresult and result.header.total > len(
            rawresult["hits"]["hits"]
        ):
            # we need to fetch all!
            consumed = len(rawresult["hits"]["hits"])

            while result.header.total > consumed:
                # xxx: dont know yet, if from_, size is better solution
                raw_res = self.connection.scroll(rawresult["_scroll_id"])
                if len(raw_res["hits"]["hits"]) == 0:
                    break

                self.extract_hits(selects, raw_res["hits"]["hits"], result.body)

                consumed += len(raw_res["hits"]["hits"])

                if result.header.total <= consumed:
                    break

        return result

    def current_url(self):
        """
        complete url from current request
        return yarl.URL"""
        raise NotImplementedError

    def wrapped_with_bundle(self, result):
        """ """
        url = self.current_url()

        wrapper = BundleWrapper(self, result, url, "searchset")
        return wrapper()
