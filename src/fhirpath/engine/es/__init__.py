# _*_ coding: utf-8 _*_
import re
from collections import defaultdict
from typing import Dict, List, Optional

from fhirspec import FHIRStructureDefinitionElement
from zope.interface import implementer

from fhirpath.engine import EngineResultRow
from fhirpath.engine.base import (
    Engine,
    EngineResult,
    EngineResultBody,
    EngineResultHeader,
)
from fhirpath.engine.es.mapping import (
    build_elements_paths,
    create_resource_mapping,
    fhir_types_mapping,
)
from fhirpath.enums import EngineQueryType
from fhirpath.exceptions import ValidationError
from fhirpath.fhirspec import FhirSpecFactory
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


class ElasticsearchEngineBase(Engine):
    def initial_bundle_data(self):
        """Can be overridden in sub class"""
        return BundleWrapper.init_data()

    def extract_hits(self, source_filters, hits, container, doc_type="_doc"):
        """ """
        for res in hits:
            if res["_type"] != doc_type:
                continue
            row = EngineResultRow()
            if len(source_filters) > 0:
                for fullpath in source_filters:
                    source = res["_source"]
                    for path_ in fullpath.split("."):
                        source = self._traverse_for_value(source, path_)
                        if source is None:
                            break
                    row.append(source)
            else:
                for resource_data in res["_source"].values():
                    row.append(resource_data)
            container.add(row)

    def build_security_query(self, query):
        """ """
        return query

    def calculate_field_index_name(self, resource_type):
        raise NotImplementedError

    def get_index_name(self, resource_type: Optional[str] = None):
        """ """
        raise NotImplementedError

    def get_mapping(self, resource_type):
        """ """
        raise NotImplementedError

    def current_url(self):
        """
        complete url from current request
        return yarl.URL"""
        raise NotImplementedError

    def wrapped_with_bundle(self, result, includes=None, as_json=False):
        """ """
        url = self.current_url()
        if includes is None:
            includes = list()
        init_data = self.initial_bundle_data()
        wrapper = BundleWrapper(
            self, result, includes, url, "searchset", init_data=init_data
        )
        return wrapper(as_json=as_json)

    def generate_mappings(
        self,
        reference_analyzer: str = None,
        token_normalizer: str = None,
    ):
        """
        You may use this function to build the ES mapping.
        Returns an object like:
        {
            "Patient": {
                "properties": {
                    "identifier": {
                        "properties": {
                            "use": {
                                "type": "keyword",
                                "index": true,
                                "store": false,
                                "fields": {
                                    "raw": {
                                        "type": "keyword"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        fhir_spec = FhirSpecFactory.from_release(self.fhir_release.name)

        resources_elements: Dict[
            str, List[FHIRStructureDefinitionElement]
        ] = defaultdict()

        for definition_klass in fhir_spec.profiles.values():
            if definition_klass.name in ("Resource", "DomainResource"):
                # exceptional
                resources_elements[definition_klass.name] = definition_klass.elements
                continue
            if definition_klass.structure.subclass_of != "DomainResource":
                # we accept domain resource only
                continue

            resources_elements[definition_klass.name] = definition_klass.elements

        elements_paths = build_elements_paths(resources_elements)

        fhir_es_mappings = fhir_types_mapping(
            self.fhir_release.name, reference_analyzer, token_normalizer
        )
        return {
            resource: {
                "properties": create_resource_mapping(paths_def, fhir_es_mappings)
            }
            for resource, paths_def in elements_paths.items()
        }

    def _traverse_for_value(self, source, path_):
        """Looks path_ is innocent string key, but may content expression, function."""
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
            if path_ == "*":
                # TODO check if we can have other keys than resource
                return source[list(source.keys())[0]]

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
                    f"Invalid path {path_} has been supplied!"
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

    def _get_source_filters(self, selects):
        """ """
        source_filters = []
        for el_path in selects:
            if el_path.star:
                source_filters.append("*")
                break
            if el_path.non_fhir is True:
                # No replacer for Non Fhir Path
                source_filters.append(el_path.path)
                continue
            parts = el_path._raw.split(".")
            source_filters.append(
                ".".join([self.calculate_field_index_name(parts[0]), *parts[1:]])
            )
        return source_filters

    def _add_result_headers(self, query, result, compiled):
        """ """
        # Process additional meta
        result.header.raw_query = self.connection.finalize_search_params(compiled)

        source_filters = self._get_source_filters(query.get_select())
        if len(source_filters) == 0:
            return

        selects = list()
        for froms in query.get_from():
            resource_type = froms[0]
            field_index_name = self.calculate_field_index_name(resource_type)
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


@implementer(IElasticsearchEngine)
class ElasticsearchEngine(ElasticsearchEngineBase):
    """Elasticsearch Engine"""

    def _execute(self, query, unrestricted, query_type):
        """ """
        query_copy = query.clone()

        if unrestricted is False:
            self.build_security_query(query_copy)

        compiled = self.dialect.compile(
            query_copy,
            calculate_field_index_name=self.calculate_field_index_name,
            get_mapping=self.get_mapping,
        )
        if query_type == EngineQueryType.DML:
            raw_result = self.connection.fetch(self.get_index_name(), compiled)
        elif query_type == EngineQueryType.COUNT:
            raw_result = self.connection.count(self.get_index_name(), compiled)
        else:
            raise NotImplementedError

        return raw_result, compiled

    def execute(self, query, unrestricted=False, query_type=EngineQueryType.DML):
        """ """
        raw_result, compiled = self._execute(query, unrestricted, query_type)
        selects = query.get_select()
        # xxx: process result
        result = self.process_raw_result(raw_result, selects, query_type)

        # Process additional meta
        self._add_result_headers(query, result, compiled)
        return result

    def process_raw_result(self, rawresult, selects, query_type):
        """ """
        if query_type == EngineQueryType.COUNT:
            total = rawresult["count"]
            source_filters = []
        # let´s make some compatibilities
        elif isinstance(rawresult["hits"]["total"], dict):
            total = rawresult["hits"]["total"]["value"]
            source_filters = self._get_source_filters(selects)
        else:
            total = rawresult["hits"]["total"]
            source_filters = self._get_source_filters(selects)

        result = EngineResult(
            header=EngineResultHeader(total=total), body=EngineResultBody()
        )

        # extract primary data
        if query_type != EngineQueryType.COUNT:
            self.extract_hits(source_filters, rawresult["hits"]["hits"], result.body)

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

                self.extract_hits(source_filters, raw_res["hits"]["hits"], result.body)

                consumed += len(raw_res["hits"]["hits"])

                if result.header.total <= consumed:
                    break

        return result


@implementer(IElasticsearchEngine)
class AsyncElasticsearchEngine(ElasticsearchEngineBase):
    """Async Elasticsearch Engine"""

    @classmethod
    def is_async(cls):
        return True

    async def _execute(self, query, unrestricted, query_type):
        """ """
        query_copy = query.clone()

        if unrestricted is False:
            self.build_security_query(query_copy)

        compiled = self.dialect.compile(
            query_copy,
            calculate_field_index_name=self.calculate_field_index_name,
            get_mapping=self.get_mapping,
        )
        if query_type == EngineQueryType.DML:
            raw_result = await self.connection.fetch(self.get_index_name(), compiled)
        elif query_type == EngineQueryType.COUNT:
            raw_result = await self.connection.count(self.get_index_name(), compiled)
        else:
            raise NotImplementedError

        return raw_result, compiled

    async def execute(self, query, unrestricted=False, query_type=EngineQueryType.DML):
        """ """
        raw_result, compiled = await self._execute(query, unrestricted, query_type)
        selects = query.get_select()
        # xxx: process result
        result = await self.process_raw_result(raw_result, selects, query_type)

        # Process additional meta
        self._add_result_headers(query, result, compiled)
        return result

    async def process_raw_result(self, rawresult, selects, query_type):
        """ """
        if query_type == EngineQueryType.COUNT:
            total = rawresult["count"]
            source_filters = []
        # let´s make some compatibilities
        elif isinstance(rawresult["hits"]["total"], dict):
            total = rawresult["hits"]["total"]["value"]
            source_filters = self._get_source_filters(selects)
        else:
            total = rawresult["hits"]["total"]
            source_filters = self._get_source_filters(selects)

        result = EngineResult(
            header=EngineResultHeader(total=total), body=EngineResultBody()
        )

        # extract primary data
        if query_type != EngineQueryType.COUNT:
            self.extract_hits(source_filters, rawresult["hits"]["hits"], result.body)

        if "_scroll_id" in rawresult and result.header.total > len(
            rawresult["hits"]["hits"]
        ):
            # we need to fetch all!
            consumed = len(rawresult["hits"]["hits"])

            while result.header.total > consumed:
                # xxx: dont know yet, if from_, size is better solution
                raw_res = await self.connection.scroll(rawresult["_scroll_id"])
                if len(raw_res["hits"]["hits"]) == 0:
                    break

                self.extract_hits(source_filters, raw_res["hits"]["hits"], result.body)

                consumed += len(raw_res["hits"]["hits"])

                if result.header.total <= consumed:
                    break

        return result
