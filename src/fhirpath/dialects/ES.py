# _*_ coding: utf-8 _*_
"""ElasticSearch Dialect"""
import operator

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
    operator.gt: "gte",
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
            elif term.arithmetic_operator == operator.pos:
                container = body_structure["query"]["bool"]["filter"]
            else:
                # xxx: if None may be should?
                raise NotImplementedError

            container.append(q)

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

                elif term.path.context.type_name == "dateTime":
                    q = {"term": {term.path.path: term.value.value}}
                    return q, term.unary_operator
            else:
                raise NotImplementedError

        else:
            raise NotImplementedError

    def resolve_datetime_term(self, term):
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

        if term.value.value.tzinfo:
            q["range"][term.path.path]["time_zone"] = term.value.value.tzinfo

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
