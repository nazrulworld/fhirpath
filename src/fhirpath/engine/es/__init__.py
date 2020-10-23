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

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"



@implementer(IElasticsearchEngine)
class ElasticsearchEngine(Engine):
    """Elasticsearch Engine"""

    def get_index_name(self, resource_type: Optional[str] = None):
        """ """
        raise NotImplementedError

    def get_mapping(self, resource_type):
        """ """
        raise NotImplementedError

    def _add_result_headers(self, query, result, compiled):
        """ """
        # Process additional meta
        result.header.raw_query = self.connection.finalize_search_params(compiled)

        element_filters = self._get_element_filters(query.get_element())
        if len(element_filters) == 0:
            return

        elements = list()
        for froms in query.get_from():
            resource_type = froms[0]
            field_index_name = self.calculate_field_index_name(resource_type)
            for path_ in element_filters:
                if not path_.startswith(field_index_name):
                    elements.append(path_)
                    continue
                parts = path_.split(".")
                if len(parts) == 1:
                    elements.append(resource_type)
                else:
                    elements.append(".".join([resource_type] + parts[1:]))

        result.header.elements = elements

    def _get_element_filters(self, elements):
        """ """
        element_filters = []
        for el_path in elements:
            if el_path.star:
                element_filters.append("*")
                break
            if el_path.non_fhir is True:
                # No replacer for Non Fhir Path
                element_filters.append(el_path.path)
                continue
            parts = el_path._raw.split(".")
            element_filters.append(
                ".".join([self.calculate_field_index_name(parts[0]), *parts[1:]])
            )
        return element_filters

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
        elements = query.get_element()
        # xxx: process result
        result = self.process_raw_result(raw_result, elements, query_type)

        # Process additional meta
        self._add_result_headers(query, result, compiled)
        return result

    def build_security_query(self, query):
        """ """
        pass

    def calculate_field_index_name(self, resource_type):
        raise NotImplementedError

    def extract_hits(self, element_filters, hits, container, doc_type="_doc"):
        """ """
        for res in hits:
            if res["_type"] != doc_type:
                continue
            row = EngineResultRow()
            for resource_data in res["_source"].values():
                row.append(resource_data)

            container.add(row)

    def process_raw_result(self, rawresult, elements, query_type):
        """ """
        if query_type == EngineQueryType.COUNT:
            total = rawresult["count"]
            element_filters = []
        # let´s make some compabilities
        elif isinstance(rawresult["hits"]["total"], dict):
            total = rawresult["hits"]["total"]["value"]
            element_filters = self._get_element_filters(elements)
        else:
            total = rawresult["hits"]["total"]
            element_filters = self._get_element_filters(elements)

        result = EngineResult(
            header=EngineResultHeader(total=total), body=EngineResultBody()
        )
        if len(elements) == 0:
            # Nothing would be in body
            return result
        # extract primary data
        if query_type != EngineQueryType.COUNT:
            self.extract_hits(element_filters, rawresult["hits"]["hits"], result.body)

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

                self.extract_hits(element_filters, raw_res["hits"]["hits"], result.body)

                consumed += len(raw_res["hits"]["hits"])

                if result.header.total <= consumed:
                    break

        return result

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
        wrapper = BundleWrapper(self, result, includes, url, "searchset")
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
