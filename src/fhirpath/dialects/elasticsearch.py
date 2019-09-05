# _*_ coding: utf-8 _*_
"""ElasticSearch Dialect"""
import logging
import operator
import re

import isodate
from zope.interface import Interface
from zope.interface import alsoProvides

from fhirpath.enums import GroupType
from fhirpath.enums import MatchType
from fhirpath.enums import SortOrderType
from fhirpath.enums import TermMatchType
from fhirpath.fql.interfaces import IExistsTerm
from fhirpath.fql.interfaces import IGroupTerm
from fhirpath.fql.interfaces import IInTerm
from fhirpath.fql.interfaces import ITerm
from fhirpath.interfaces import IFhirPrimitiveType

from .base import DialectBase


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"
logger = logging.getLogger("fhirpath.dialects.elasticsearch")
URI_SCHEME = re.compile(r"^https?://", re.I)
ES_PY_OPERATOR_MAP = {
    operator.eq: None,
    operator.ne: None,
    operator.gt: "gt",
    operator.lt: "lt",
    operator.ge: "gte",
    operator.le: "lte",
}


class IIgnoreNestedCheck(Interface):
    """Marker interface"""


class ElasticSearchDialect(DialectBase):
    """ """

    def _apply_nested(self, query, dotted_path):
        """ """
        wrapper = {
            "nested": {
                "path": dotted_path,
                "query": query,
                "ignore_unmapped": False,
                "score_mode": "min",
            }
        }
        return wrapper

    def _apply_path_replacement(self, dotted_path, root_replacer):
        """ """
        if root_replacer is not None:
            path_ = ".".join([root_replacer] + list(dotted_path.split(".")[1:]))
        else:
            path_ = dotted_path
        return path_

    def _attach_nested_on_demand(self, context, query_, root_replacer):
        """ """
        path_context = context
        qr = query_

        while True:
            if path_context.multiple and not IFhirPrimitiveType.implementedBy(
                path_context.type_class
            ):
                path_ = self._apply_path_replacement(
                    str(path_context._path), root_replacer
                )
                qr = self._apply_nested(qr, path_)
            if path_context.is_root():
                break
            path_context = path_context.parent

        return qr

    def _create_term(self, term, root_replacer=None):
        """Create ES Query term"""
        if root_replacer is not None:
            path_ = ".".join([root_replacer] + list(term.path.path.split(".")[1:]))
        else:
            path_ = term.path.path
        if term.path.context.multiple:
            q = {"terms": {path_: [term.value.value]}}
        else:
            q = {"term": {path_: term.value.value}}

        return q

    def _clean_up(self, body_structure):
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

    def _get_path_mapping_info(self, mapping, dotted_path):
        """ """
        mapping_ = mapping["properties"]

        for path_ in dotted_path.split(".")[1:]:
            try:
                info_ = mapping_[path_]
            except KeyError:
                logger.warn("No mapping found for {0}".format(dotted_path))
                return {}
            if "properties" in info_:
                mapping_ = info_["properties"]
            else:
                return info_

    def compile(self, query, mapping, root_replacer=None, security_callable=None):
        """
        :param: query
        :param: mapping: Elasticsearch mapping for FHIR resources.
        :root_replacer: Path´s root replacer:
        Could be mapping name or index name in zope´s ZCatalog context
        :security_callable:
        """
        body_structure = self.create_structure()
        conditional_terms = query.get_where()

        for term in conditional_terms:
            """ """
            q, unary_operator = self.resolve_term(term, mapping, root_replacer)

            if unary_operator == operator.neg:
                container = body_structure["query"]["bool"]["must_not"]
            elif unary_operator == operator.pos:
                container = body_structure["query"]["bool"]["filter"]
            else:
                # xxx: if None may be should?
                from inspect import currentframe, getframeinfo

                frameinfo = getframeinfo(currentframe())
                raise NotImplementedError(
                    "File: {0} Line: {1}".format(
                        frameinfo.filename, frameinfo.lineno + 1
                    )
                )

            container.append(q)

        self.apply_limit(query.get_limit(), body_structure)

        if security_callable is not None:
            securities = security_callable()
            self.apply_security(securities, body_structure)

        self.apply_from_constraint(query, body_structure, root_replacer=root_replacer)

        self._clean_up(body_structure)

        if "should" in body_structure["query"]["bool"]:
            if "minimum_should_match" not in body_structure["query"]["bool"]:
                body_structure["query"]["bool"]["minimum_should_match"] = 1

        return body_structure

    def resolve_term(self, term, mapping, root_replacer):
        """ """
        if IGroupTerm.providedBy(term):
            unary_operator = operator.pos
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

            elif term.type == GroupType.COUPLED:
                qr = {"bool": {"filter": list()}}
                container = qr["bool"]["filter"]
            else:
                raise NotImplementedError

            for t_ in term.terms:
                # single term resolver should not look at this
                alsoProvides(t_, IIgnoreNestedCheck)

                resolved = self.resolve_term(t_, mapping, root_replacer)
                container.append(resolved[0])

            qr = self._attach_nested_on_demand(term.path.context, qr, root_replacer)

            return qr, unary_operator

        elif IInTerm.providedBy(term):
            raise NotImplementedError

        elif IExistsTerm.providedBy(term):
            return self.resolve_exists_term(term, root_replacer=root_replacer)

        elif ITerm.providedBy(term):
            if IFhirPrimitiveType.implementedBy(term.path.context.type_class):

                if term.path.context.type_name in (
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
                    # xxx: may do something special?
                    if root_replacer is not None:
                        path_ = ".".join(
                            [root_replacer] + list(term.path.path.split(".")[1:])
                        )
                    else:
                        path_ = term.path.path

                    map_info = self._get_path_mapping_info(mapping, path_)

                    if map_info.get("type", None) == "text":
                        resolved = self.resolve_string_term(
                            term, map_info, root_replacer
                        )

                    else:
                        q = self._create_term(term, root_replacer)
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

                    resolved = self.resolve_numeric_term(term, root_replacer)
                else:
                    raise NotImplementedError

                if IIgnoreNestedCheck.providedBy(term):
                    return resolved

                # check for nested
                qr, unary_operator = resolved
                qr = self._attach_nested_on_demand(term.path.context, qr, root_replacer)
                return qr, unary_operator
            else:
                raise NotImplementedError("Line 85")

        else:
            raise NotImplementedError

    def resolve_datetime_term(self, term, root_replacer=None):
        """TODO: 1.) Value Conversion(stringify) based of context.type_name
        i.e date or dateTime or Time """
        q = dict()
        type_name = term.path.context.type_name
        if root_replacer is not None:
            path_ = ".".join([root_replacer] + list(term.path.path.split(".")[1:]))
        else:
            path_ = term.path.path

        if type_name in ("dateTime", "instant"):
            value_formatter = (
                isodate.DATE_EXT_COMPLETE + "T" + isodate.TIME_EXT_COMPLETE
            )
        elif type_name == "date":
            value_formatter = isodate.DATE_EXT_COMPLETE
        elif type_name == "time":
            value_formatter = isodate.TIME_EXT_COMPLETE
        else:
            raise NotImplementedError

        if term.comparison_operator in (operator.eq, operator.ne):
            q["range"] = {
                path_: {
                    ES_PY_OPERATOR_MAP[operator.ge]: isodate.strftime(
                        term.value.value, value_formatter
                    ),
                    ES_PY_OPERATOR_MAP[operator.le]: isodate.strftime(
                        term.value.value, value_formatter
                    ),
                }
            }

        elif term.comparison_operator in (
            operator.le,
            operator.lt,
            operator.ge,
            operator.gt,
        ):
            q["range"] = {
                path_: {
                    ES_PY_OPERATOR_MAP[term.comparison_operator]: isodate.strftime(
                        term.value.value, value_formatter
                    )
                }
            }

        if type_name in ("dateTime", "instant", "time") and term.value.value.tzinfo:
            timezone = isodate.tz_isoformat(term.value.value)
            if timezone not in ("", "Z"):
                q["range"][path_]["time_zone"] = timezone

        if (
            term.comparison_operator != operator.ne
            and term.unary_operator == operator.neg
        ) or (
            term.comparison_operator == operator.ne
            and term.unary_operator != operator.neg
        ):
            unary_operator = operator.neg
        else:
            unary_operator = operator.pos

        return q, unary_operator

    def resolve_numeric_term(self, term, root_replacer=None):
        """ """
        q = dict()

        if root_replacer is not None:
            path_ = ".".join([root_replacer] + list(term.path.path.split(".")[1:]))
        else:
            path_ = term.path.path

        if term.comparison_operator in (operator.eq, operator.ne):
            q["range"] = {
                path_: {
                    ES_PY_OPERATOR_MAP[operator.ge]: term.value.value,
                    ES_PY_OPERATOR_MAP[operator.le]: term.value.value,
                }
            }

        elif term.comparison_operator in (
            operator.le,
            operator.lt,
            operator.ge,
            operator.gt,
        ):
            q["range"] = {
                path_: {ES_PY_OPERATOR_MAP[term.comparison_operator]: term.value.value}
            }

        if (
            term.comparison_operator != operator.ne
            and term.unary_operator == operator.neg
        ) or (
            term.comparison_operator == operator.ne
            and term.unary_operator != operator.neg
        ):
            unary_operator = operator.neg
        else:
            unary_operator = operator.pos

        return q, unary_operator

    def resolve_string_term(self, term, map_info, root_replacer=None):
        """ """
        # xxx: could have support for free text search
        q = dict()

        if root_replacer is not None:
            path_ = ".".join([root_replacer] + list(term.path.path.split(".")[1:]))
        else:
            path_ = term.path.path

        fulltext_analyzers = ("standard",)
        val = term.value.value
        if map_info.get("analyzer", "standard") in fulltext_analyzers:
            # xxx: should handle exact match
            if term.match_type == TermMatchType.EXACT:
                q = {"match_phrase": {path_: val}}
            else:
                q = {"match": {path_: val}}
        elif ("/" in val or URI_SCHEME.match(val)) and ".reference" in path_:
            q = {"match_phrase": {path_: val}}
        else:
            q = self._create_term(term, root_replacer)

        resolved = q, term.unary_operator
        return resolved

    def resolve_exists_term(self, term, root_replacer=None):
        """ """
        qr = dict()
        path_ = self._apply_path_replacement(term.path.path, root_replacer)

        qr = {"exists": {"field": path_}}

        qr = self._attach_nested_on_demand(term.path.context, qr, root_replacer)

        return qr, term.unary_operator

    def apply_security(self, securities, body_structure):
        """ """
        should_list = list()
        for field in securities:
            values = securities[field]
            if isinstance(values, (str, bytes)):
                values = [values]
            for val in values:
                if IFhirPrimitiveType.providedBy(val):
                    if val.__visit_name__ == "dateTime":
                        # just validation
                        val.to_python()
                        range_ = {
                            field: {
                                ES_PY_OPERATOR_MAP[operator.ge]: val,
                                ES_PY_OPERATOR_MAP[operator.le]: val,
                            }
                        }
                        should_list.append({"range": range_})
                    else:
                        raise NotImplementedError
                elif isinstance(val, (str, bytes)):
                    should_list.append({"match": {field: val}})
                else:
                    raise NotImplementedError

        body_structure["query"]["bool"]["filter"].append(
            {"bool": {"should": should_list, "minimum_should_match": 1}}
        )

    def apply_limit(self, limit_clause, body_structure):
        """ """
        if limit_clause.empty:
            # no limit! should be scroll
            body_structure["scroll"] = "1m"
            return
        if isinstance(limit_clause.limit, int):
            body_structure["size"] = limit_clause.limit
        if isinstance(limit_clause.offset, int):
            body_structure["from"] = limit_clause.offset

    def apply_sort(self, sort_terms, root_replacer=None):
        """ """
        for term in sort_terms:
            if root_replacer is not None:
                path_ = ".".join([root_replacer] + list(term.path.path.split(".")[1:]))
            else:
                path_ = term.path.path
            item = {
                path_: {"order": term.order == SortOrderType.DESC and "desc" or "asc"}
            }
            self.sort.append(item)

    def apply_from_constraint(self, query, body_structure, root_replacer=None):
        """We force apply resource type boundary"""
        for res_name, res_klass in query.get_from():
            path_ = "{0}.resourceType".format(root_replacer or res_name)
            term = {"term": {path_: res_name}}
            body_structure["query"]["bool"]["filter"].append(term)

    def create_structure(self):
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
        }
