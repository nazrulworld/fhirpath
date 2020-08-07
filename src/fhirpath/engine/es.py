# _*_ coding: utf-8 _*_
import re
from typing import Optional

from zope.interface import implementer

from fhirpath.engine import EngineResultRow
from fhirpath.engine.base import (
    Engine,
    EngineResult,
    EngineResultBody,
    EngineResultHeader,
)
from fhirpath.enums import EngineQueryType
from fhirpath.exceptions import ValidationError
from fhirpath.interfaces import IElasticsearchEngine
from fhirpath.utils import BundleWrapper

CONTAINS_INDEX_OR_FUNCTION = re.compile(r"[a-z09_]+(\[[0-9]+\])|(\([0-9]*\))$", re.I)
CONTAINS_INDEX = re.compile(r"[a-z09_]+\[[0-9]+\]$", re.I)
CONTAINS_FUNCTION = re.compile(r"[a-z09_]+\([0-9]*\)$", re.I)

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def navigate_indexed_path(source, path_):
    """ """
    parts = path_.split("[")
    p_ = parts[0]
    index = int(parts[1][:-1])
    value = source.get(p_, None)
    if value is None:
        return value

    try:
        return value[index]
    except IndexError:
        return None


@implementer(IElasticsearchEngine)
class ElasticsearchEngine(Engine):
    """Elasticsearch Engine"""

    def get_index_name(self, resource_type: Optional[str] = None):
        """ """
        raise NotImplementedError

    def get_mapping(self, resource_type):
        """ """
        raise NotImplementedError

    def _add_result_headers(
        self, query, result, source_filters, compiled, field_index_name
    ):
        """ """
        # Process additional meta
        result.header.raw_query = self.connection.finalize_search_params(compiled)
        if len(source_filters) == 0:
            return

        resource_type = query.get_from()[0][0]
        selects = list()
        for path_ in source_filters:
            if not path_.startswith(field_index_name):
                selects.append(path_)
                continue
            parts = path_.split(".")
            if len(parts) == 1:
                selects.append(resource_type)
            else:
                selects.append(".".join([resource_type] + parts[1:]))

        result.header.selects = selects

    def _get_source_filters(self, query, field_index_name):
        """ """
        source_filters = []
        for el_path in query.get_select():
            if el_path.star:
                source_filters.append(field_index_name)
                break
            if el_path.non_fhir is True:
                # No replacer for Non Fhir Path
                source_filters.append(el_path.path)
                continue
            parts = el_path._raw.split(".")
            source_filters.append(".".join([field_index_name] + parts[1:]))
        return source_filters

    def _traverse_for_value(self, source, path_):
        """Looks path_ is innocent string key, but may content expression, function.
        """
        if isinstance(source, dict):
            # xxx: validate path, not blindly sending None
            if CONTAINS_INDEX_OR_FUNCTION.search(path_) and CONTAINS_FUNCTION.match(
                path_
            ):
                raise ValidationError(
                    f"Invalid path {path_} has been supllied!"
                    "Path cannot contain function if source type is dict"
                )
            if CONTAINS_INDEX.match(path_):
                return navigate_indexed_path(source, path_)

            return source.get(path_, None)

        elif isinstance(source, list):
            if not CONTAINS_FUNCTION.match(path_):
                raise ValidationError(
                    f"Invalid path {path_} has been supllied!"
                    "Path should contain function if source type is list"
                )
            parts = path_.split("(")
            func_name = parts[0]
            index = None
            if len(parts[1]) > 1:
                index = int(parts[1][:-1])
            if func_name == "count":
                return len(source)
            elif func_name == "first":
                return source[0]
            elif func_name == "last":
                return source[-1]
            elif func_name == "Skip":
                new_order = list()
                for idx, no in enumerate(source):
                    if idx == index:
                        continue
                    new_order.append(no)
                return new_order
            elif func_name == "Take":
                try:
                    return source[index]
                except IndexError:
                    return None
            else:
                raise NotImplementedError
        elif isinstance(source, (bytes, str)):
            if not CONTAINS_FUNCTION.match(path_):
                raise ValidationError(
                    f"Invalid path {path_} has been supllied!"
                    "Path should contain function if source type is list"
                )
            parts = path_.split("(")
            func_name = parts[0]
            index = len(parts[1]) > 1 and int(parts[1][:-1]) or None
            if func_name == "count":
                return len(source)
            else:
                raise NotImplementedError

        else:
            raise NotImplementedError

    def _execute(self, query, unrestricted, query_type):
        """ """
        # for now we support single from resource
        query_copy = query.clone()

        resource_type = query.get_from()[0][1].get_resource_type()
        field_index_name = self.calculate_field_index_name(resource_type)

        if unrestricted is False:
            self.build_security_query(query_copy)

        params = {
            "query": query_copy,
            "root_replacer": field_index_name,
            "mapping": self.get_mapping(resource_type),
        }

        compiled = self.dialect.compile(**params)
        if query_type == EngineQueryType.DML:
            raw_result = self.connection.fetch(self.get_index_name(), compiled)
        elif query_type == EngineQueryType.COUNT:
            raw_result = self.connection.count(self.get_index_name(), compiled)
        else:
            raise NotImplementedError

        return raw_result, field_index_name, compiled

    def execute(self, query, unrestricted=False, query_type=EngineQueryType.DML):
        """ """
        raw_result, field_index_name, compiled = self._execute(
            query, unrestricted, query_type
        )
        if query_type == EngineQueryType.COUNT:
            source_filters = []
        else:
            source_filters = self._get_source_filters(query, field_index_name)

        # xxx: process result
        result = self.process_raw_result(raw_result, source_filters)

        # Process additional meta
        self._add_result_headers(
            query, result, source_filters, compiled, field_index_name
        )
        return result

    def build_security_query(self, query):
        """ """
        pass

    def calculate_field_index_name(self, resource_type):
        raise NotImplementedError

    def extract_hits(self, selects, hits, container, doc_type="_doc"):
        """ """
        for res in hits:
            if res["_type"] != doc_type:
                continue
            row = EngineResultRow()
            for fullpath in selects:
                source = res["_source"]
                for path_ in fullpath.split("."):
                    source = self._traverse_for_value(source, path_)
                    if source is None:
                        break
                row.append(source)
            container.add(row)

    def process_raw_result(self, rawresult, selects):
        """ """
        if len(selects) == 0 and "count" in rawresult:
            # Might be count API
            total = rawresult["count"]
        # let´s make some compabilities
        elif isinstance(rawresult["hits"]["total"], dict):
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
