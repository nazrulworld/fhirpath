# _*_ coding: utf-8 _*_
"""ElasticSearch Dialect"""
import operator

import isodate

from fhirpath.fql.interfaces import IExistsTerm
from fhirpath.fql.interfaces import IGroupTerm
from fhirpath.fql.interfaces import IInTerm
from fhirpath.fql.interfaces import ITerm
from fhirpath.interfaces import IFhirPrimitiveType

from .base import DialectBase


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

ES_PY_OPERATOR_MAP = {
    operator.eq: None,
    operator.ne: None,
    operator.gt: "gt",
    operator.lt: "lt",
    operator.ge: "gte",
    operator.le: "lte",
}


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

    def compile(self, query, root_replacer=None):
        """
        :param: query
        :root_replacer: Path´s root replacer:
        Could be mapping name or index name in zope´s ZCatalog context
        """
        body_structure = self.create_structure()
        conditional_terms = query.get_where()

        for term in conditional_terms:
            """ """
            q, unary_operator = self.resolve_term(term, root_replacer)

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

        self._clean_up(body_structure)

        if "should" in body_structure["query"]["bool"]:
            if "minimum_should_match" not in body_structure["query"]["bool"]:
                body_structure["query"]["bool"]["minimum_should_match"] = 1

        return body_structure

    def resolve_term(self, term, root_replacer):
        """ """
        if IGroupTerm.providedBy(term):
            qr = {"bool": {"filter": list()}}
            container = qr["bool"]["filter"]

            for t_ in term.terms:
                q, unary_operator = self.resolve_term(t_, root_replacer)
                container.append(q)

            path_context = term.path.context

            while True:
                if path_context.multiple:
                    path_ = self._apply_path_replacement(
                        str(path_context._path), root_replacer
                    )
                    qr = self._apply_nested(qr, path_)
                if path_context.is_root():
                    break
                path_context = path_context.parent

            return qr, operator.pos

        elif IInTerm.providedBy(term):
            raise NotImplementedError

        elif IExistsTerm.providedBy(term):
            raise NotImplementedError

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
                    if term.path.context.multiple:
                        q = {"terms": {path_: [term.value.value]}}
                    else:
                        q = {"term": {path_: term.value.value}}

                    return q, term.unary_operator

                elif term.path.context.type_name in (
                    "dateTime",
                    "date",
                    "time",
                    "instant",
                ):

                    return self.resolve_datetime_term(term, root_replacer)

                elif term.path.context.type_name in (
                    "integer",
                    "decimal",
                    "unsignedInt",
                    "positiveInt",
                ):

                    return self.resolve_numeric_term(term, root_replacer)
                else:
                    raise NotImplementedError
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
            "sort": list()
        }
