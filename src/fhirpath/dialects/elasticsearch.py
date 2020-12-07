# _*_ coding: utf-8 _*_
"""ElasticSearch Dialect"""
import logging
import re

import isodate
from zope.interface import alsoProvides

from fhirpath.enums import OPERATOR, GroupType, MatchType, SortOrderType, TermMatchType
from fhirpath.interfaces import IFhirPrimitiveType, IPrimitiveTypeCollection
from fhirpath.interfaces.dialects import IIgnoreNestedCheck
from fhirpath.interfaces.fql import (
    IExistsTerm,
    IGroupTerm,
    IInTerm,
    INonFhirTerm,
    ITerm,
)

from .base import DialectBase

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"
logger = logging.getLogger("fhirpath.dialects.elasticsearch")
URI_SCHEME = re.compile(r"^https?://", re.I)
ES_PY_OPERATOR_MAP = {
    OPERATOR.eq: None,
    OPERATOR.ne: None,
    OPERATOR.gt: "gt",
    OPERATOR.lt: "lt",
    OPERATOR.ge: "gte",
    OPERATOR.le: "lte",
}


def escape_star(v):
    """ """
    if "*" in v:
        v = v.replace("*", "\\*")
    return v


def escape_all(v):
    """ """
    v = escape_star(v)
    v = (
        v.replace(".", "\\.")
        .replace("?", "\\?")
        .replace(":", "\\:")
        .replace("[", "\\[")
    )
    return v


class ElasticSearchDialect(DialectBase):
    """ """

    @staticmethod
    def apply_nested(query, dotted_path):
        """ """
        wrapper = {
            "nested": {
                "path": dotted_path,
                "query": query,
                "ignore_unmapped": True,
                "score_mode": "min",
            }
        }
        return wrapper

    @staticmethod
    def apply_path_replacement(dotted_path, root_replacer):
        """ """
        if root_replacer is not None:
            path_ = ".".join([root_replacer] + list(dotted_path.split(".")[1:]))
        else:
            path_ = dotted_path
        return path_

    @staticmethod
    def attach_nested_on_demand(context, query_, root_replacer):
        """ """
        path_context = context
        qr = query_

        if path_context.resource_type == "Resource":
            # FIXME ugly: no nested query if we search on all types because
            # Resource.meta is of type nested but with option "include_in_root"
            # set to True
            return qr

        while True:
            if path_context.multiple and not path_context.type_is_primitive:
                path_ = ElasticSearchDialect.apply_path_replacement(
                    str(path_context._path), root_replacer
                )
                qr = ElasticSearchDialect.apply_nested(qr, path_)
            if path_context.is_root():
                break
            path_context = path_context.parent

        return qr

    @staticmethod
    def create_term(path, value, multiple=False, match_type=None, all_resources=False):
        """Create ES Query term"""
        multiple_ = isinstance(value, (list, tuple)) or multiple is True
        if multiple_ is True and not isinstance(value, (list, tuple)):
            value = [value]

        if all_resources:
            # TODO is there a better way to search on all resource types?
            # TODO does it work if both all_resources and multiple_ are True?
            q = {"multi_match": {"query": value, "fields": [path]}}
        elif match_type == TermMatchType.EXACT and not multiple_:
            q = {"term": {f"{path}.raw": value}}
        elif match_type == TermMatchType.EXACT and multiple_:
            q = {"terms": {f"{path}.raw": value}}
        elif match_type != TermMatchType.EXACT and multiple_:
            q = {"terms": {path: value}}
        else:
            q = {"match": {path: value}}

        return q

    @staticmethod
    def create_sa_term(path, value):
        """Create ES Prefix Query"""
        if isinstance(value, (list, tuple)):
            if len(value) == 1:
                value = value[0]
            else:
                q = {"bool": {"should": [], "minimum_should_match": 1}}
                for val in value:
                    q["bool"]["should"].append({"prefix": {path: {"value": val}}})
                return q

        q = {"prefix": {path: {"value": value}}}

        return q

    @staticmethod
    def create_contains_term(path, value):
        """Create ES Regex Query"""

        if isinstance(value, (list, tuple)):
            if len(value) == 1:
                value = value[0]
            else:
                q = {"bool": {"should": [], "minimum_should_match": 1}}
                for val in value:
                    q["bool"]["should"].append(
                        {"prefix": {path: {"value": ".*{0}.*".format(escape_all(val))}}}
                    )
                return q

        q = {"regexp": {path: {"value": ".*{0}.*".format(escape_all(value))}}}

        return q

    @staticmethod
    def create_eb_term(path, value):
        """Create ES Prefix Query"""
        if isinstance(value, (list, tuple)):
            if len(value) == 1:
                value = value[0]
            else:
                q = {"bool": {"should": [], "minimum_should_match": 1}}
                for val in value:
                    q["bool"]["should"].append(
                        {"wildcard": {path: {"value": "*" + escape_star(val)}}}
                    )
                return q

        q = {"wildcard": {path: {"value": "*{0}".format(escape_star(value))}}}

        return q

    @staticmethod
    def create_dotted_path(term, root_replacer=None):
        """ """
        if INonFhirTerm.providedBy(term):
            return term.path

        if root_replacer is not None:
            path_ = ".".join([root_replacer] + list(term.path.path.split(".")[1:]))
        else:
            path_ = term.path.path
        return path_

    @staticmethod
    def clean_up(body_structure):
        """ """
        if len(body_structure["query"]["bool"]["should"]) == 0:
            del body_structure["query"]["bool"]["should"]

        if len(body_structure["query"]["bool"]["must"]) == 0:
            del body_structure["query"]["bool"]["must"]

        if len(body_structure["query"]["bool"]["must_not"]) == 0:
            del body_structure["query"]["bool"]["must_not"]

        if len(body_structure["query"]["bool"]["filter"]) == 0:
            del body_structure["query"]["bool"]["filter"]

        if len(body_structure["sort"]) == 0:
            del body_structure["sort"]

        if body_structure["_source"] is not False:

            if len(body_structure["_source"]["includes"]) == 0:
                del body_structure["_source"]["includes"]

            if len(body_structure["_source"]["excludes"]) == 0:
                del body_structure["_source"]["excludes"]

            if len(body_structure["_source"]) == 0:
                del body_structure["_source"]

    @staticmethod
    def get_path_mapping_info(mapping, dotted_path):
        """ """
        mapping_ = mapping["properties"]

        for path_ in dotted_path.split(".")[1:]:
            try:
                info_ = mapping_[path_]
            except KeyError:
                logger.warning("No mapping found for {0}".format(dotted_path))
                return {}
            if "properties" in info_:
                mapping_ = info_["properties"]
            else:
                return info_

    def compile_for_single_resource_type(
        self, query, resource_type, mapping=None, root_replacer=None
    ):
        """
        :param: query

        :param: mapping: Elasticsearch mapping for FHIR resources.

        :root_replacer: Path´s root replacer:
            Could be mapping name or index name in zope´s ZCatalog context
        """
        body_structure = ElasticSearchDialect.create_structure()
        conditional_terms = [
            w
            for w in query.get_where()
            if (
                not INonFhirTerm.providedBy(w)
                and w.path.context.resource_type == resource_type
            )
            or INonFhirTerm.providedBy(w)
        ]
        for term in conditional_terms:
            q, unary_operator = self.resolve_term(term, mapping, root_replacer)

            if unary_operator == OPERATOR.neg:
                container = body_structure["query"]["bool"]["must_not"]
            elif unary_operator == OPERATOR.pos:
                container = body_structure["query"]["bool"]["filter"]
            else:
                # xxx: if None may be should?
                from inspect import currentframe, getframeinfo

                frameinfo = getframeinfo(currentframe())
                raise NotImplementedError(
                    f"File: {frameinfo.filename} Line: {frameinfo.lineno + 1}"
                )

            container.append(q)

        # if not searching on all resources, add a predicate to filter on resourceType
        if resource_type != "Resource":
            ElasticSearchDialect.apply_from_constraint(
                query, body_structure, resource_type, root_replacer=root_replacer
            )

        # Sorting
        ElasticSearchDialect.apply_sort(
            query.get_sort(), body_structure, root_replacer=root_replacer
        )
        # Limit
        ElasticSearchDialect.apply_limit(query.get_limit(), body_structure)
        # ES source_
        ElasticSearchDialect.apply_source_filter(
            query, body_structure, root_replacer=root_replacer
        )

        ElasticSearchDialect.clean_up(body_structure)

        if "should" in body_structure["query"]["bool"]:
            if "minimum_should_match" not in body_structure["query"]["bool"]:
                body_structure["query"]["bool"]["minimum_should_match"] = 1

        return body_structure

    def compile(self, query, calculate_field_index_name, get_mapping):
        """ """
        query_fragments = []

        for from_clause in query.get_from():
            resource_type = from_clause[1].get_resource_type()
            field_index_name = calculate_field_index_name(resource_type)
            mapping = get_mapping(resource_type)

            query_fragments.append(
                self.compile_for_single_resource_type(
                    query,
                    resource_type=resource_type,
                    mapping=mapping,
                    root_replacer=field_index_name,
                )
            )
        if len(query_fragments) == 0:
            # Search on all types: available searchparams use
            # "Resource" as path.context.resource_type
            # Use "*" as root_replacer to match any resource across the ES mapping.
            return self.compile_for_single_resource_type(
                query,
                resource_type="Resource",
                mapping=None,
                root_replacer="*",
            )
        elif len(query_fragments) > 1:
            return {
                "query": {
                    "bool": {
                        "should": [frag["query"] for frag in query_fragments],
                        "minimum_should_match": 1,
                    }
                }
            }
        else:
            return query_fragments[0]

    def resolve_term(self, term, mapping, root_replacer):
        """ """
        if IGroupTerm.providedBy(term):
            unary_operator = OPERATOR.pos
            if term.type == GroupType.DECOUPLED:

                if term.match_operator == MatchType.ANY:
                    qr = {"bool": {"should": list()}}
                    container = qr["bool"]["should"]
                    qr["bool"]["minimum_should_match"] = 1

                elif term.match_operator == MatchType.ALL:
                    qr = {"bool": {"filter": list()}}
                    container = qr["bool"]["filter"]

                elif term.match_operator == MatchType.NONE:
                    qr = {"bool": {"must_not": list()}}
                    container = qr["bool"]["must_not"]

                alsoProvides(term, IIgnoreNestedCheck)

            elif term.type == GroupType.COUPLED:
                if term.match_operator == MatchType.NONE:
                    qr = {"bool": {"must_not": list()}}
                    container = qr["bool"]["must_not"]
                else:
                    qr = {"bool": {"filter": list()}}
                    container = qr["bool"]["filter"]
            else:
                raise NotImplementedError

            for t_ in term.terms:
                # single term resolver should not look at this
                if term.type == GroupType.COUPLED:
                    alsoProvides(t_, IIgnoreNestedCheck)

                resolved, operator = self.resolve_term(t_, mapping, root_replacer)
                if operator == OPERATOR.neg:
                    container.append({"bool": {"must_not": [resolved]}})
                else:
                    container.append(resolved)

            if not IIgnoreNestedCheck.providedBy(term):
                qr = ElasticSearchDialect.attach_nested_on_demand(
                    term.path.context, qr, root_replacer
                )

            return qr, unary_operator

        elif IInTerm.providedBy(term):

            unary_operator = term.unary_operator
            qr = {"bool": {"should": list()}}
            container = qr["bool"]["should"]

            for t_ in term:
                resolved = self.resolve_term(t_, mapping, root_replacer)
                container.append(resolved[0])
            if len(container) > 0:
                qr["bool"]["minimum_should_match"] = 1
            return qr, unary_operator

        elif IExistsTerm.providedBy(term):
            return ElasticSearchDialect.resolve_exists_term(
                term, root_replacer=root_replacer
            )

        elif ITerm.providedBy(term):

            if term.path.context.type_is_primitive:

                if term.path.context.type_name in (
                    "string",
                    "xhtml",
                    "uri",
                    "url",
                    "canonical",
                    "code",
                    "oid",
                    "id",
                    "uuid",
                    "boolean",
                ):
                    # xxx: may do something special?
                    multiple = term.path.context.multiple
                    dotted_path = ElasticSearchDialect.create_dotted_path(
                        term, root_replacer
                    )
                    value = term.get_real_value()

                    # FIXME when searching on all resources, we don't have the mapping
                    map_info = (
                        ElasticSearchDialect.get_path_mapping_info(mapping, dotted_path)
                        if mapping
                        else None
                    )

                    if map_info and map_info.get("type", None) == "text":
                        resolved = ElasticSearchDialect.resolve_string_term(
                            term, map_info, root_replacer
                        )

                    else:
                        if term.comparison_operator == OPERATOR.sa:
                            q = ElasticSearchDialect.create_sa_term(dotted_path, value)
                        elif term.comparison_operator == OPERATOR.eb:
                            q = ElasticSearchDialect.create_eb_term(dotted_path, value)
                        elif term.comparison_operator == OPERATOR.contains:
                            q = ElasticSearchDialect.create_contains_term(
                                dotted_path, value
                            )
                        else:
                            # FIXME find a cleaner way to do that
                            # If root_replacer is "*", we're searching on all resources
                            all_resources = root_replacer == "*"
                            q = ElasticSearchDialect.create_term(
                                dotted_path,
                                value,
                                multiple=multiple,
                                match_type=term.match_type,
                                all_resources=all_resources,
                            )
                        resolved = q, term.unary_operator

                elif term.path.context.type_name in (
                    "dateTime",
                    "date",
                    "time",
                    "instant",
                ):

                    resolved = self.resolve_datetime_term(term, root_replacer)

                elif term.path.context.type_name in (
                    "integer",
                    "decimal",
                    "unsignedInt",
                    "positiveInt",
                ):

                    resolved = ElasticSearchDialect.resolve_numeric_term(
                        term, root_replacer
                    )
                else:
                    raise NotImplementedError

                if IIgnoreNestedCheck.providedBy(term):
                    return resolved

                # check for nested
                qr, unary_operator = resolved
                qr = ElasticSearchDialect.attach_nested_on_demand(
                    term.path.context, qr, root_replacer
                )
                return qr, unary_operator
            else:
                raise NotImplementedError("Line 425")

        elif INonFhirTerm.providedBy(term):
            assert IFhirPrimitiveType.providedBy(term.value)
            return self.resolve_nonfhir_term(term)

    def resolve_datetime_term(self, term, root_replacer=None):
        """ """
        qr = dict()

        value = term.get_real_value()
        path_ = ElasticSearchDialect.create_dotted_path(term, root_replacer)

        if hasattr(value, "day") and hasattr(value, "hour"):
            value_formatter = (
                isodate.DATE_EXT_COMPLETE + "T" + isodate.TIME_EXT_COMPLETE
            )
        elif hasattr(value, "day"):
            value_formatter = isodate.DATE_EXT_COMPLETE
        elif hasattr(value, "hour"):
            value_formatter = isodate.TIME_EXT_COMPLETE
        else:
            raise ValueError("Could not understand date query value.")

        if term.comparison_operator in (OPERATOR.eq, OPERATOR.ne):
            qr["range"] = {
                path_: {
                    ES_PY_OPERATOR_MAP[OPERATOR.ge]: isodate.strftime(
                        value, value_formatter
                    ),
                    ES_PY_OPERATOR_MAP[OPERATOR.le]: isodate.strftime(
                        value, value_formatter
                    ),
                }
            }

        elif term.comparison_operator in (
            OPERATOR.le,
            OPERATOR.lt,
            OPERATOR.ge,
            OPERATOR.gt,
        ):
            qr["range"] = {
                path_: {
                    ES_PY_OPERATOR_MAP[term.comparison_operator]: isodate.strftime(
                        value, value_formatter
                    )
                }
            }

        if hasattr(value, "tzinfo") and value.tzinfo:
            timezone = isodate.tz_isoformat(value)
            if timezone not in ("", "Z"):
                qr["range"][path_]["time_zone"] = timezone

        if (
            term.comparison_operator != OPERATOR.ne
            and term.unary_operator == OPERATOR.neg
        ) or (
            term.comparison_operator == OPERATOR.ne
            and term.unary_operator != OPERATOR.neg
        ):
            unary_operator = OPERATOR.neg
        else:
            unary_operator = OPERATOR.pos

        return qr, unary_operator

    @staticmethod
    def resolve_numeric_term(term, root_replacer=None):
        """ """
        qr = dict()
        path_ = ElasticSearchDialect.create_dotted_path(term, root_replacer)
        value = term.get_real_value()

        if term.comparison_operator in (OPERATOR.eq, OPERATOR.ne):
            qr["range"] = {
                path_: {
                    ES_PY_OPERATOR_MAP[OPERATOR.ge]: value,
                    ES_PY_OPERATOR_MAP[OPERATOR.le]: value,
                }
            }

        elif term.comparison_operator in (
            OPERATOR.le,
            OPERATOR.lt,
            OPERATOR.ge,
            OPERATOR.gt,
        ):
            qr["range"] = {path_: {ES_PY_OPERATOR_MAP[term.comparison_operator]: value}}

        if (
            term.comparison_operator != OPERATOR.ne
            and term.unary_operator == OPERATOR.neg
        ) or (
            term.comparison_operator == OPERATOR.ne
            and term.unary_operator != OPERATOR.neg
        ):
            unary_operator = OPERATOR.neg
        else:
            unary_operator = OPERATOR.pos

        return qr, unary_operator

    @staticmethod
    def resolve_string_term(term, map_info, root_replacer=None):
        """ """
        # xxx: could have support for free text search
        path_ = ElasticSearchDialect.create_dotted_path(term, root_replacer)

        custom_analyzer = map_info.get("analyzer")
        fulltext_analyzers = (None, "standard")
        value = term.get_real_value()

        # when searching on a reference, the field must have been
        # analyzed in a custom way.
        if (
            not term.path.context.is_root()
            and term.path.context._get_parent().type_name == "Reference"
        ):
            if custom_analyzer is None:
                logger.warning(f"No custom analyzer found for reference {path_}")
            if term.comparison_operator == OPERATOR.sa:
                qr = {"match_phrase_prefix": {path_: value}}
            else:
                qr = {"term": {path_: value}}

        # if a fulltext analyzer is configured, produce a full-text query
        elif custom_analyzer in fulltext_analyzers:

            if term.match_type == TermMatchType.EXACT:
                qr = {"match_phrase": {path_: value}}
            elif term.comparison_operator == OPERATOR.sa:
                qr = {"match_phrase_prefix": {path_: value}}
            elif term.comparison_operator == OPERATOR.eb:
                qr = {
                    "query_string": {
                        "fields": [path_],
                        "query": "*{0}".format(escape_star(value)),
                    }
                }
            elif term.comparison_operator == OPERATOR.contains:
                qr = {
                    "query_string": {
                        "fields": [path_],
                        "query": "*{0}*".format(escape_star(value)),
                    }
                }
            else:
                qr = {"match": {path_: {"query": value, "fuzziness": "AUTO"}}}

        # fallback on a regular query
        else:
            qr = ElasticSearchDialect.create_term(
                path_, value, term.path.context.multiple
            )

        return qr, term.unary_operator

    @staticmethod
    def resolve_exists_term(term, root_replacer=None):
        """ """
        path_ = ElasticSearchDialect.create_dotted_path(term, root_replacer)

        qr = {"exists": {"field": path_}}
        if not INonFhirTerm.providedBy(term):
            qr = ElasticSearchDialect.attach_nested_on_demand(
                term.path.context, qr, root_replacer
            )

        return qr, term.unary_operator

    def resolve_nonfhir_term(self, term):
        """ """
        if IPrimitiveTypeCollection.providedBy(term.value):
            visit_name = term.value.registered_visit
            if visit_name in ("string", "code", "oid", "id", "uuid"):
                if visit_name == "string" and term.match_type not in (
                    None,
                    TermMatchType.EXACT,
                ):
                    raise ValueError(
                        "PrimitiveTypeCollection instance is not "
                        "allowed if match type not exact"
                    )
            else:
                raise NotImplementedError
        else:
            visit_name = term.value.__visit_name__

        if visit_name in (
            "string",
            "uri",
            "url",
            "canonical",
            "code",
            "oid",
            "id",
            "uuid",
            "boolean",
        ):
            if term.match_type not in (TermMatchType.FULLTEXT, None):
                resolved = ElasticSearchDialect.resolve_string_term(term, {}, None)
            else:
                value = term.get_real_value()
                q = ElasticSearchDialect.create_term(term.path, value)
                resolved = q, term.unary_operator

        elif visit_name in ("dateTime", "date", "time", "instant"):

            resolved = self.resolve_datetime_term(term, None)

        elif visit_name in ("integer", "decimal", "unsignedInt", "positiveInt"):

            resolved = ElasticSearchDialect.resolve_numeric_term(term, None)
        else:
            raise NotImplementedError
        return resolved

    @staticmethod
    def apply_limit(limit_clause, body_structure):
        """ """
        if limit_clause.empty:
            # no limit! should be scroll
            body_structure["scroll"] = "1m"
            return
        if isinstance(limit_clause.limit, int):
            body_structure["size"] = limit_clause.limit
        if isinstance(limit_clause.offset, int):
            body_structure["from"] = limit_clause.offset

    @staticmethod
    def apply_sort(sort_terms, body_structure, root_replacer=None):
        """ """
        for term in sort_terms:
            if root_replacer is not None:
                path_ = ".".join([root_replacer] + list(term.path.path.split(".")[1:]))
            else:
                path_ = term.path.path
            item = {
                # https://www.elastic.co/guide/en/elasticsearch/\
                # reference/current/search-request-body.html#_ignoring_unmapped_fields
                path_: {
                    "order": term.order == SortOrderType.DESC and "desc" or "asc",
                    "unmapped_type": "long",
                }
            }
            body_structure["sort"].append(item)

    @staticmethod
    def apply_from_constraint(query, body_structure, resource_type, root_replacer=None):
        """We force apply resource type boundary"""
        path_ = f"{root_replacer or resource_type}.resourceType"
        term = {"match": {path_: resource_type}}
        body_structure["query"]["bool"]["filter"].append(term)

    @staticmethod
    def apply_source_filter(query, body_structure, root_replacer=None):
        """https://www.elastic.co/guide/en/elasticsearch/reference/\
        current/search-request-body.html#request-body-search-source-filtering

            1.) we are using FHIR field data from ES server directly, unlike collective.
                elasticsearch, where only path is retrieve, then using that set
                zcatalog brain, this patternt might good for
                general puporse but here we exclusively need fhir
                resource only which is already stored in ES.
                Our approach will be definately performance optimized!

            2.) We might loose minor security (only zope specific),
                because here permission is not checking while getting full object.
        """

        if len(query.get_element()) == 0:
            # No select no source!
            body_structure["_source"] = False
            return

        def replace(path_el):
            if root_replacer is None or path_el.non_fhir:
                return path_el.path
            parts = path_el.path.split(".")
            if len(parts) > 1:
                return ".".join([root_replacer] + list(parts[1:]))
            else:
                return root_replacer

        includes = list()
        if len(query.get_element()) == 1 and query.get_element()[0].star:
            if root_replacer is None:
                includes.append(query.get_from()[0][0])
            else:
                includes.append(root_replacer)
        elif len(query.get_element()) > 0:
            # always include the resourceType in the ES response
            includes.append(
                f"{root_replacer}.resourceType" if root_replacer else "resourceType"
            )
            for path_el in query.get_element():
                includes.append(replace(path_el))

        if len(includes) > 0:
            body_structure["_source"]["includes"].extend(includes)

    @staticmethod
    def create_structure():
        """ """
        return {
            "query": {
                "bool": {
                    "should": list(),
                    "must": list(),
                    "must_not": list(),
                    "filter": list(),
                }
            },
            "size": 100,
            "from": 0,
            "sort": list(),
            "_source": {"includes": [], "excludes": []},
        }
