# _*_ coding: utf-8 _*_
import re
from urllib.parse import unquote_plus

from multidict import MultiDict
from multidict import MultiDictProxy
from zope.interface import Invalid
from zope.interface import implementer

from fhirpath.enums import FHIR_VERSION
from fhirpath.exceptions import ValidationError
from fhirpath.fql import G_
from fhirpath.fql import Q_
from fhirpath.fql import T_
from fhirpath.fql import V_
from fhirpath.fql import in_
from fhirpath.fql import not_
from fhirpath.fql.types import ElementPath
from fhirpath.interfaces import IFhirPrimitiveType
from fhirpath.interfaces import ISearch
from fhirpath.interfaces import ISearchContext
from fhirpath.storage import SEARCH_PARAMETERS_STORAGE
from fhirpath.thirdparty import at_least_one_of
from fhirpath.thirdparty import mutually_exclusive_parameters


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

escape_comma_replacer = "_ESCAPE_COMMA_"
uri_scheme = re.compile(r"^https?://", re.I)
value_prefixes = {"eq", "ne", "gt", "lt", "ge", "le", "sa", "eb", "ap"}
has_dot_as = re.compile(r"\.as\([a-z]+\)$", re.I ^ re.U)
has_dot_is = re.compile(r"\.is\([a-z]+\)$", re.I ^ re.U)
has_dot_where = re.compile(r"\.where\([a-z\=\'\"()]+\)", re.I ^ re.U)


def has_escape_comma(val):
    return "\\," in val


@implementer(ISearchContext)
class SearchContext(object):
    """ """

    __slots__ = ("resource_name", "engine")

    def __init__(self, engine, resource_type):
        """ """
        object.__setattr__(self, "engine", engine)
        object.__setattr__(self, "resource_name", resource_type)


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

        _containedType = all_params.popone("_containedType", None)
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

        for param_name in self.search_params:
            """ """
            normalized = self.normalize_param(param_name)
            self.add_term(self, builder, normalized)

    def add_term(self, builder, normalized_data):
        """ """
        param_name, param_value, modifier = normalized_data
        path_ = self.resolve_path_context(param_name)

        if path_._where is not None:
            raise NotImplementedError
        elif path_._is is not None:
            raise NotImplementedError
        elif path_._as is not None:
            raise NotImplementedError

        if not IFhirPrimitiveType.implementedBy(path_.context.type_class):
            # we need normalization
            klass_name = path_.context.type_class.__class__.__name__

            if klass_name == "Reference":
                path_ = path_ / "reference"
                path_.finalize(self.context.engine)

    def create_identifier_term(self, param_name, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_identifier_term(param_name, value, modifier)
                terms.append(term)
            group = G_(*terms)
            return group

        elif isinstance(param_value, tuple):
            path_ = self.resolve_path_context(param_name)
            return self.single_valued_identifier_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_identifier_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        has_pipe = "|" in original_value

        if modifier == "text" and not has_pipe:
            # xxx: should be validation error if value contained pipe
            # make identifier.type.text query
            path_ = path_ / "type" / "text"
            return self.create_term(path_, value, modifier)

        elif has_pipe:
            if original_value.startswith("|"):
                path_ = path_ / "value"
                new_value = (operator_, original_value[1:])
                return self.create_term(path_, new_value, modifier)
            elif original_value.endswith("|"):
                path_ = path_ / "system"
                new_value = (value[0], original_value[:-1])
                return self.create_term(path_, new_value, modifier)

            else:
                parts = original_value.split("|")
                terms = list()
                try:
                    path_1 = path_ / "value"
                    new_value = (operator_, parts[0])
                    term = self.create_term(path_1, new_value, modifier)
                    terms.append(term)

                    path_2 = path_ / "system"
                    new_value = (operator_, parts[1])
                    term = self.create_term(path_2, new_value, modifier)
                    terms.append(term)

                except IndexError:
                    pass

                if len(terms) > 1:
                    return G_(*terms)
                else:
                    return terms[0]
        else:
            path_1 = path_ / "value"
            return self.create_term(path_1, value, modifier)

    def create_quantity_term(self, param_name, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_quantity_term(param_name, value, modifier)
                terms.append(term)
            group = G_(*terms)
            return group

        elif isinstance(param_value, tuple):
            path_ = self.resolve_path_context(param_name)
            return self.single_valued_quantity_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_quantity_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        operator_eq = "eq"
        has_pipe = "|" in original_value
        # modifier = text, no impact
        if has_pipe:
            terms = list()
            parts = original_value.split("|")

            if len(parts) == 3:
                path_1 = path_ / "value"
                new_value = (operator_, parts[0])
                term = self.create_term(path_1, new_value, modifier)
                terms.append(term)

                if parts[1]:
                    # check if val||unit or codeß
                    path_2 = path_ / "system"
                    new_value = (operator_eq, parts[1])
                    term = self.create_term(path_2, new_value, modifier)
                    terms.append(term)

                    path_3 = path_ / "code"
                    new_value = (operator_eq, parts[2])
                    term = self.create_term(path_3, new_value, modifier)
                    terms.append(term)
                else:
                    path_2 = path_ / "unit"
                    new_value = (operator_eq, parts[2])
                    term = self.create_term(path_2, new_value, modifier)
                    terms.append(term)

            else:
                # may be validation error
                raise NotImplementedError

            if len(terms) > 1:
                return G_(*terms)
            else:
                return terms[0]
        else:
            path_1 = path_ / "value"
            return self.create_term(path_1, value, modifier)

    def create_coding_term(self, param_name, param_value, modifier):
        """ """

        search_param = getattr(self.definition, param_name)
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_coding_term(param_name, value, modifier)
                terms.append(term)
            group = G_(*terms)
            return group

        elif isinstance(param_value, tuple):
            path_ = ElementPath.from_el_path(
                search_param.expression, self.context.engine.fhir_release
            )
            path_.finalize(self.context.engine)

            return self.single_valued_coding_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_coding_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        has_pipe = "|" in original_value

        if modifier == "text" and not has_pipe:
            # xxx: should be validation error if value contained pipe
            # make identifier.type.text query
            path_ = path_ / "display"
            return self.create_term(path_, value, modifier)

        elif has_pipe:
            if original_value.startswith("|"):
                path_ = path_ / "code"
                new_value = (value[0], original_value[1:])
                return self.create_term(path_, new_value, modifier)
            elif original_value.endswith("|"):
                path_ = path_ / "system"
                new_value = (value[0], original_value[:-1])
                return self.create_term(path_, new_value, modifier)

            else:
                parts = original_value.split("|")
                terms = list()
                try:
                    path_1 = path_ / "system"
                    new_value = (value[0], parts[0])
                    term = self.create_term(path_1, new_value, modifier)
                    terms.append(term)

                    path_2 = path_ / "code"
                    new_value = (value[0], parts[1])
                    term = self.create_term(path_2, new_value, modifier)
                    terms.append(term)

                except IndexError:
                    pass

                if len(terms) > 1:
                    return G_(*terms)
                else:
                    return terms[0]
        else:
            path_1 = path_ / "code"
            return self.create_term(path_1, value, modifier)

    def create_codeableconcept_term(self, param_name, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_codeableconcept_term(param_name, value, modifier)
                terms.append(term)
            group = G_(*terms)
            return group

        elif isinstance(param_value, tuple):
            path_ = self.resolve_path_context(param_name)
            return self.single_valued_codeableconcept_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_codeableconcept_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        has_pipe = "|" in original_value

        if modifier == "text" and not has_pipe:
            # xxx: should be validation error if value contained pipe
            # make identifier.type.text query
            path_ = path_ / "text"
            return self.create_term(path_, value, modifier)

        else:
            path_1 = path_ / "coding"
            return self.single_valued_coding_term(path_1, value, modifier)

    def validate_pre_term(self, path_, value, modifier):
        """ """
        pass

    def create_term(self, path_, value, modifier):
        """ """
        assert IFhirPrimitiveType.implementedBy(path_.context.type_class)

        if isinstance(value, tuple):
            operator_, original_value = value
            if isinstance(original_value, list):
                # we force IN will have equal or not equal operator_
                # xxx: should be validated already
                term = in_(path_, original_value)
                if modifier == "not":
                    term = not_(term)
                return term

            term = T_(path_)
            if modifier == "not":
                term = not_(term)

            val = V_(original_value)

            if operator_ == "eq":
                term = term == val
            elif operator_ == "ne":
                term = term != val
            elif operator_ == "lt":
                term = term < val
            elif operator_ == "le":
                term = term <= val
            elif operator_ == "gt":
                term = term > val
            elif operator_ == "ge":
                term = term >= val
            else:
                raise NotImplementedError

            return term

        elif isinstance(value, list):
            # Group Term
            terms = list()
            for val in value:
                term = self.create_term(path_, val, modifier)
                terms.append(term)

            g_term = G_(*terms)
            return g_term

    def normalize_param_value(self, raw_value, container):
        """ """
        if isinstance(raw_value, list):
            for rv in raw_value:
                self.normalize_param_value(rv, container)
        else:
            escape_ = has_escape_comma(raw_value)
            if escape_:
                param_value = raw_value.replace("\\,", escape_comma_replacer)
            else:
                param_value = raw_value

            value_parts = param_value.split(",")
            comparison_operator = "eq"

            if len(value_parts) == 1:
                if escape_:
                    value = value_parts[0].replace(escape_comma_replacer, "\\,")
                else:
                    value = value_parts[0]

                for prefix in value_prefixes:
                    if value.startswith(prefix):
                        comparison_operator = prefix
                        value = value[2:]
                        break
            else:
                value = list()
                for val in value_parts:
                    if escape_:
                        val = val.replace(escape_comma_replacer, "\\,")
                    for prefix in value_prefixes:
                        if val.startswith(prefix):
                            # should not come here, may be pre validated!
                            # Just cleanup, for IN term only equal or not equal allowed
                            val = val[2:]
                            break
                    value.append(val)

            container.append((comparison_operator, value))

    def normalize_param(self, param_name):
        """ """
        raw_value = list(self.search_params.getall(param_name, []))
        if len(raw_value) == 0:
            raw_value = None
        elif len(raw_value) == 1:
            raw_value = raw_value[0]

        try:
            parts = param_name.split(":")
            param_name_ = parts[0]
            modifier_ = parts[1]
        except IndexError:
            modifier_ = None

        values = list()
        self.normalize_param_value(raw_value, values)

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
        search_param = getattr(self.definition, param_name, None)
        if search_param is None:
            raise ValidationError(
                "No search definition is available for search parameter "
                "``{param_name}`` on Resource ``{self.context.resource_name}``."
            )

        if search_param.expression is None:
            raise NotImplementedError
        path_ = ElementPath.from_el_path(search_param.expression)
        path_.finalize(self.context.engine)

        return path_
