# _*_ coding: utf-8 _*_
import re
from urllib.parse import unquote_plus

from multidict import MultiDict
from multidict import MultiDictProxy
from zope.interface import Invalid
from zope.interface import implementer

from fhirpath.enums import FHIR_VERSION
from fhirpath.exceptions import ValidationError
from fhirpath.fql import Q_
from fhirpath.fql.types import ElementPath
from fhirpath.interfaces import ISearch
from fhirpath.interfaces import ISearchContext
from fhirpath.storage import SEARCH_PARAMETERS_STORAGE
from fhirpath.thirdparty import at_least_one_of
from fhirpath.thirdparty import mutually_exclusive_parameters
from fhirpath.utils import PathInfoContext


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

escape_comma_replacer = "_ESCAPE_COMMA_"
uri_scheme = re.compile(r"^https?://", re.I)
value_prefixes = {"eq" "ne", "gt", "lt", "ge", "le", "sa", "eb", "ap"}
has_dot_as = re.compile(r"\.as\([a-z]+\)$", re.I ^ re.U)
has_dot_is = re.compile(r"\.is\([a-z]+\)$", re.I ^ re.U)
has_dot_where = re.compile(r"\.where\([a-z\=\'\"\(\)]+)", re.I ^ re.U)


def has_escape_comma(val):
    return "\\," in val


@implementer(ISearchContext)
class SearchContext(object):
    """ """

    __slots__ = ("resource_name", "engine")


@implementer(ISearch)
class Search(object):
    """ """

    @at_least_one_of("query_string", "params")
    @mutually_exclusive_parameters("query_string", "params")
    def __init__(self, context, query_string=None, params=None):
        """ """
        self.context = ISearchContext(context)
        if query_string:
            all_params = Search.parse_query_string(query_string, False)
        elif isinstance(params, (tuple, list)):
            all_params = MultiDict(params)
        elif isinstance(params, dict):
            all_params = MultiDict(params.items())
        elif isinstance(params, MultiDictProxy):
            all_params = params.copy()
        else:
            raise Invalid

        self.result_params = dict()
        self.search_params = None

        self.prepare_params(all_params)

        self.definition = Search.get_parameter_definition(
            self.context.engine.fhir_release, self.context.resource_name
        )

        self.builder = None

    def prepare_params(self, all_params):
        """makeing search, sort, limit, params
        Result Parameters
        ~~~~~~~~~~~~~~~~
        _sort
        _count
        _include
        _revinclude
        _summary
        _total
        _elements
        _contained
        _containedType
        """
        _sort = all_params.popall("_sort", [])
        if len(_sort) > 0:
            self.result_params["_sort"] = ",".join(_sort)

        _count = all_params.popall("_count", [])

        if len(_count) > 0:
            if len(_count) > 1:
                raise ValidationError("'_count' cannot be multiple!")
            self.result_params["_count"] = _count[0]

        _total = all_params.popall("_total", [])

        if len(_total) > 0:
            if len(_total) > 1:
                raise ValidationError("'_total' cannot be multiple!")
            self.result_params["_total"] = _total[0]

        _summary = all_params.popone("_summary", None)
        if _summary:
            self.result_params["_summary"] = _summary

        _include = all_params.popone("_include", None)
        if _include:
            self.result_params["_include"] = _include

        _revinclude = all_params.popone("_revinclude", None)
        if _revinclude:
            self.result_params["_revinclude"] = _revinclude

        _elements = all_params.popone("_elements", [])
        if len(_elements) > 0:
            self.result_params["_elements"] = ",".join(_elements)

        _contained = all_params.popone("_contained", None)
        if _contained:
            self.result_params["_contained"] = _contained

        _containedType = self.all_params.popone("_containedType", None)
        if _containedType:
            self.result_params["_containedType"] = _containedType

        self.search_params = MultiDictProxy(all_params)

    @staticmethod
    def parse_query_string(query_string, allow_none=False):
        """
        param:request
        param:allow_none
        """
        params = MultiDict()

        for q in query_string.split("&"):
            parts = q.split("=")
            param_name = unquote_plus(parts[0])
            try:
                value = parts[1] and unquote_plus(parts[1]) or None
            except IndexError:
                if not allow_none:
                    continue
                value = None

            params.add(param_name, value)

        return MultiDictProxy(params)

    @classmethod
    def from_query_string(cls, query_string):
        """ """

    @staticmethod
    def get_parameter_definition(fhir_release: FHIR_VERSION, resource_name: str):
        """ """
        storage = SEARCH_PARAMETERS_STORAGE.get(fhir_release.value)

        if storage.empty():
            """Need to load first """
            from fhirpath.fhirspec import FHIRSearchSpecFactory

            spec = FHIRSearchSpecFactory.from_release(fhir_release.value)
            spec.write()

        return storage.get(resource_name)

    def build(self):
        """Create QueryBuilder from search query string"""
        builder = Q_(self.context.resource_name, self.context.engine)

        for param_name, param_value in self.search_params.items():
            """ """
            normalized = self.normalize_param(param_name, param_value)
            self.add_term(self, builder, normalized)

    def add_term(self, builder, normalized_data):
        """ """
        param_name, param_value, modifier = normalized_data
        search_param = getattr(self.definition, param_name)
        path_context = None
        path_ = None

        if has_dot_as.search(search_param.expression):
            raise NotImplementedError
        elif has_dot_as.search(search_param.expression):
            raise NotImplementedError
        elif has_dot_where.search(search_param.expression):
            raise NotImplementedError
        elif search_param.expression is None:
            raise NotImplementedError
        else:
            path_ = ElementPath(search_param.expression)
            path_context = PathInfoContext.context_from_path(str(path_))
            if path_context is None:
                raise LookupError(
                    "'{0!s}' is not valid FHIR Path".format(path_)
                )

    def create_term(self, path_, value, modifier):
        """ """


    def normalize_param(self, param_name, param_value):
        """ """
        try:
            parts = param_name.split(":")
            param_name_ = parts[0]
            modifier_ = parts[1]
        except IndexError:
            modifier_ = None

        escape_ = has_escape_comma(param_value)
        if escape_:
            param_value_ = param_value.replace("\\,", escape_comma_replacer)
        else:
            param_value_ = param_value

        values = list()
        for val in param_value_.split(","):
            val = val.replace(escape_comma_replacer, "\\,")
            comparison_operator = "eq"
            for prefix in value_prefixes:
                if val.startswith(prefix):
                    comparison_operator = prefix
                    val = val[2:]
                    break

            values.append((val, comparison_operator))

        if len(values) == 1:
            param_value_ = values[0]
        else:
            param_value_ = values

        return param_name_, param_value_, modifier_

    def validate(self):
        """ """
        unwanted = set()

        for param_name in self.search_params:

            if param_name.split(":")[0] not in self.definition:
                unwanted.add(param_name)

        if len(unwanted) > 0:
            raise ValidationError(
                "({0}) search parameter(s) are not "
                "available for resource `{1}`.".format(
                    ", ".join([u for u in unwanted]), self.context.resource_name
                )
            )
        # xxx: later more

    def validate_normalized_value(self, normalized):
        """ """
        param_name, param_value, modifier = normalized

    def resolve_path_context(self, param_name):
        """ """
        search_param = getattr(self.definition, param_name)
