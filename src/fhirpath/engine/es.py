# _*_ coding: utf-8 _*_
from zope.interface import implementer

from fhirpath.engine import Engine
from fhirpath.engine import EngineResult
from fhirpath.engine import EngineResultBody
from fhirpath.engine import EngineResultHeader
from fhirpath.interfaces import IElasticsearchEngine
from fhirpath.utils import BundleWrapper


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


@implementer(IElasticsearchEngine)
class ElasticsearchEngine(Engine):
    """Elasticsearch Engine"""

    def get_index_name(self):
        """ """
        raise NotImplementedError

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
        """ """
        return {}

    def calculate_field_index_name(self, resource_type):
        raise NotImplementedError

    def extract_hits(self, hits, container):
        """ """
        raise NotImplementedError

    def process_raw_result(self, rawresult, fieldname):
        """ """
        # let´s make some compabilities
        if isinstance(rawresult["hits"]["total"], dict):
            total = rawresult["hits"]["total"]["value"]
        else:
            total = rawresult["hits"]["total"]

        header = EngineResultHeader(total=total)
        body = EngineResultBody()

        # extract primary data
        self.extract_hits(rawresult["hits"]["hits"], body)

        if "_scroll_id" in rawresult and header.total > len(rawresult["hits"]["hits"]):
            # we need to fetch all!
            consumed = len(rawresult["hits"]["hits"])

            while header.total > consumed:
                # xxx: dont know yet, if from_, size is better solution
                raw_res = self.connection.scroll(rawresult["_scroll_id"])
                if len(raw_res["hits"]["hits"]) == 0:
                    break

                self.extract_hits(raw_res["hits"]["hits"], body)

                consumed += len(raw_res["hits"]["hits"])

                if header.total <= consumed:
                    break

        return EngineResult(header=header, body=body)

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
