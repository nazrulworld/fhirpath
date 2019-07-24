# _*_ coding: utf-8 _*_
"""ElasticSearch Dialect"""
import operator
import isodate

from fhirpath.interfaces import IFhirPrimitiveType
from fhirpath.fql.interfaces import IExistsTerm
from fhirpath.fql.interfaces import IGroupTerm
from fhirpath.fql.interfaces import IInTerm
from fhirpath.fql.interfaces import ITerm

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

    def compile(self, query, root_replacer=None):
        """
        :param: query
        :root_replacer: Path´s root replacer
        """
        body_structure = self.create_structure()
        conditional_terms = query.get_where()

        for term in conditional_terms:
            """ """
            q, unary_operator = self.resolve_term(term)

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

        return body_structure

    def resolve_term(self, term):
        """ """
        if IGroupTerm.providedBy(term):
            pass
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
                    if term.path.context.multiple:
                        q = {"terms": {term.path.path: [term.value.value]}}
                    else:
                        q = {"term": {term.path.path: term.value.value}}

                    return q, term.unary_operator

                elif term.path.context.type_name in (
                    "dateTime",
                    "date",
                    "time",
                    "instant",
                ):

                    return self.resolve_datetime_term(term)
                else:
                    raise NotImplementedError
            else:
                raise NotImplementedError("Line 85")

        else:
            raise NotImplementedError

    def resolve_datetime_term(self, term):
        """TODO: 1.) Value Conversion(stringify) based of context.type_name
        i.e date or dateTime or Time """
        q = dict()
        type_name = term.path.context.type_name
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
                term.path.path: {
                    operator.ge: isodate.strftime(term.value.value, value_formatter),
                    operator.le: isodate.strftime(term.value.value, value_formatter),
                }
            }

        elif term.comparison_operator in (
            operator.le,
            operator.lt,
            operator.ge,
            operator.gt,
        ):
            q["range"] = {
                term.path.path: {
                    ES_PY_OPERATOR_MAP[term.comparison_operator]: isodate.strftime(
                        term.value.value, value_formatter
                    )
                }
            }

        if type_name in ("dateTime", "instant", "time") and term.value.value.tzinfo:
            timezone = isodate.tz_isoformat(term.value.value)
            if timezone not in ("", "Z"):
                q["range"][term.path.path]["time_zone"] = timezone

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

    def resolve_numeric_term(self, term):
        """ """
        q = dict()
        if term.comparison_operator in (operator.eq, operator.ne):
            q["range"] = {
                term.path.path: {
                    operator.ge: term.value.value,
                    operator.le: term.value.value,
                }
            }

        elif term.comparison_operator in (
            operator.le,
            operator.lt,
            operator.ge,
            operator.gt,
        ):
            q["range"] = {
                term.path.path: {
                    ES_PY_OPERATOR_MAP[term.comparison_operator]: term.value.value
                }
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
            "size": 0,
            "from": 100,
            "sort": list(),
        }
