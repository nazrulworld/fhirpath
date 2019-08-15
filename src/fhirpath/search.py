# _*_ coding: utf-8 _*_
import logging
import re
from urllib.parse import unquote_plus

from multidict import MultiDict
from multidict import MultiDictProxy
from zope.interface import Invalid
from zope.interface import implementer

from fhirpath.enums import FHIR_VERSION
from fhirpath.enums import GroupType
from fhirpath.enums import MatchType
from fhirpath.enums import SortOrderType
from fhirpath.enums import WhereConstraintType
from fhirpath.exceptions import ValidationError
from fhirpath.fql import G_
from fhirpath.fql import Q_
from fhirpath.fql import T_
from fhirpath.fql import V_
from fhirpath.fql import exists_
from fhirpath.fql import in_
from fhirpath.fql import not_
from fhirpath.fql import not_exists_
from fhirpath.fql import sort_
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
logger = logging.getLogger("fhirpath.search")


def has_escape_comma(val):
    return "\\," in val


@implementer(ISearchContext)
class SearchContext(object):
    """ """

    __slots__ = ("resource_name", "engine", "unrestricted", "async_result")

    def __init__(self, engine, resource_type, unrestricted=False, async_result=False):
        """ """
        object.__setattr__(self, "engine", engine)
        object.__setattr__(self, "resource_name", resource_type)
        object.__setattr__(self, "unrestricted", unrestricted)
        object.__setattr__(self, "async_result", async_result)


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
            self.result_params["_count"] = int(_count[0])

        page = all_params.popall("page", [])
        if len(page) > 0:
            if len(page) > 1:
                raise ValidationError("'page' cannot be multiple!")
            self.result_params["page"] = int(page[0])

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

    @classmethod
    def from_params(cls, context, params):
        """ """
        return cls(context, params=params)

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
        terms_container = list()
        # making sure no duplicate keys, important!
        for param_name in set(self.search_params):
            """ """
            normalized_data = self.normalize_param(param_name)
            self.add_term(normalized_data, terms_container)

        result = self.attach_limit_terms(
            self.attach_sort_terms(builder.where(*terms_container))
        )(
            unrestricted=self.context.unrestricted,
            async_result=self.context.async_result,
        )
        return result

    def add_term(self, normalized_data, terms_container):
        """ """
        param_name, param_value, modifier = normalized_data
        path_ = self.resolve_path_context(param_name)

        if path_._where is not None:
            if path_._where.type == WhereConstraintType.T3:
                # we know what to do
                raise NotImplementedError
        elif path_._is is not None:
            raise NotImplementedError
        elif path_._as is not None:
            raise NotImplementedError

        if modifier in ("missing", "exists"):
            term = self.create_exists_term(path_, param_value, modifier)

        elif not IFhirPrimitiveType.implementedBy(path_.context.type_class):
            # we need normalization
            klass_name = path_.context.type_class.__name__
            if klass_name == "FHIRReference":
                path_ = path_ / "reference"
                term_factory = self.create_term
            elif klass_name == "Identifier":
                term_factory = self.create_identifier_term
            elif klass_name == "Quantity":
                term_factory = self.create_quantity_term
            elif klass_name == "CodeableConcept":
                term_factory = self.create_codeableconcept_term
            elif klass_name == "Coding":
                term_factory = self.create_coding_term
            elif klass_name == "Address":
                term_factory = self.create_address_term
            elif klass_name == "ContactPoint":
                term_factory = self.create_contactpoint_term
            elif klass_name == "HumanName":
                term_factory = self.create_humanname_term
            elif klass_name == "Money":
                term_factory = self.create_money_term
            else:
                raise NotImplementedError
            term = term_factory(path_, param_value, modifier)
        else:
            term = self.create_term(path_, param_value, modifier)

        terms_container.append(term)

    def create_identifier_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_identifier_term(path_, value, modifier)
                terms.append(term)
            # IN Like Group
            group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_identifier_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_identifier_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        has_pipe = "|" in original_value
        terms = list()

        if modifier == "text" and not has_pipe:
            # xxx: should be validation error if value contained pipe
            # make identifier.type.text query
            path_1 = path_ / "type" / "text"
            term = self.create_term(path_1, value, modifier)

            terms.append(term)

        elif has_pipe:
            if original_value.startswith("|"):
                path_1 = path_ / "value"
                new_value = (operator_, original_value[1:])

                term = self.create_term(path_1, new_value, modifier)
                terms.append(term)

            elif original_value.endswith("|"):
                path_1 = path_ / "system"
                new_value = (value[0], original_value[:-1])

                term = self.create_term(path_1, new_value, modifier)
                terms.append(term)

            else:
                parts = original_value.split("|")
                try:
                    path_1 = path_ / "system"
                    new_value = (operator_, parts[0])
                    term = self.create_term(path_1, new_value, modifier)
                    terms.append(term)

                    path_2 = path_ / "value"
                    new_value = (operator_, parts[1])
                    term = self.create_term(path_2, new_value, modifier)
                    terms.append(term)

                except IndexError:
                    pass

        else:
            path_1 = path_ / "value"
            term = self.create_term(path_1, value, modifier)
            terms.append(term)

        return G_(*terms, path=path_, type_=GroupType.COUPLED)

    def create_quantity_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_quantity_term(path_, value, modifier)
                terms.append(term)
            group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)

            return group

        elif isinstance(param_value, tuple):
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
                    # check if val||unit or code
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
                return G_(*terms, path=path_, type_=GroupType.COUPLED)
            else:
                return terms[0]
        else:
            path_1 = path_ / "value"
            return self.create_term(path_1, value, modifier)

    def create_coding_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_coding_term(path_, value, modifier)
                terms.append(term)
            group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_coding_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_coding_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        has_pipe = "|" in original_value
        terms = list()

        if modifier == "text" and not has_pipe:
            # xxx: should be validation error if value contained pipe
            # make identifier.type.text query
            path_1 = path_ / "display"

            term = self.create_term(path_1, value, modifier)
            terms.append(term)

        elif has_pipe:
            if original_value.startswith("|"):
                path_1 = path_ / "code"
                new_value = (value[0], original_value[1:])

                term = self.create_term(path_1, new_value, modifier)
                terms.append(term)

            elif original_value.endswith("|"):
                path_1 = path_ / "system"
                new_value = (value[0], original_value[:-1])

                terms.append(self.create_term(path_1, new_value, modifier))

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
        else:
            path_1 = path_ / "code"
            terms.append(self.create_term(path_1, value, modifier))

        return G_(*terms, path=path_, type_=GroupType.COUPLED)

    def create_codeableconcept_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_codeableconcept_term(path_, value, modifier)
                terms.append(term)
            group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_codeableconcept_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_codeableconcept_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        has_pipe = "|" in original_value

        if modifier == "text" and not has_pipe:
            # xxx: should be validation error if value contained pipe
            # make identifier.type.text query
            terms = list()
            path_1 = path_ / "text"
            terms.append(self.create_term(path_1, value, modifier))
            return G_(*terms, path=path_, type_=GroupType.COUPLED)

        else:
            path_1 = path_ / "coding"
            return self.single_valued_coding_term(path_1, value, modifier)

    def create_address_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_address_term(path_, value, modifier)
                terms.append(term)
            group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_address_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_address_term(self, path_, value, modifier):
        """ """
        if modifier == "text":
            return self.create_term(path_ / "text", value, None)

        terms = [
            self.create_term(path_ / "city", value, None),
            self.create_term(path_ / "country", value, None),
            self.create_term(path_ / "postalCode", value, None),
            self.create_term(path_ / "state", value, None),
        ]
        group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
        if modifier == "not":
            group.match_operator = MatchType.NONE
        else:
            group.match_operator = MatchType.ANY

        return group

    def create_contactpoint_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_contactpoint_term(path_, value, modifier)
                terms.append(term)
            group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_contactpoint_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_contactpoint_term(self, path_, value, modifier):
        """ """
        if path_._where:
            if path_._where.type != WhereConstraintType.T1:
                raise NotImplementedError

            assert path_._where.name == "system"

            terms = [
                self.create_term(
                    path_ / "system", (value[0], path_._where.value), None
                ),
                self.create_term(path_ / "value", value, None),
            ]
        else:
            terms = [
                self.create_term(path_ / "system", value, None),
                self.create_term(path_ / "use", value, None),
                self.create_term(path_ / "value", value, None),
            ]
        group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
        if modifier == "not":
            group.match_operator = MatchType.NONE
        else:
            group.match_operator = MatchType.ANY

        return group

    def create_humanname_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_humanname_term(path_, value, modifier)
                terms.append(term)
            group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_humanname_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_humanname_term(self, path_, value, modifier):
        """ """
        if modifier == "text":
            return self.create_term(path_ / "text", value, None)

        terms = [
            self.create_term(path_ / "family", value, None),
            self.create_term(path_ / "given", value, None),
            self.create_term(path_ / "prefix", value, None),
            self.create_term(path_ / "suffix", value, None),
        ]
        group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
        if modifier == "not":
            group.match_operator = MatchType.NONE
        else:
            group.match_operator = MatchType.ANY

        return group

    def create_reference_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_reference_term(path_, value, modifier)
                terms.append(term)
            group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_reference_term(path_, param_value, modifier)

    def single_valued_reference_term(self, path_, value, modifier):
        """ """
        if path_._where:
            if path_._where.type != WhereConstraintType.T2:
                raise NotImplementedError
            assert path_._where.value is not None

            logger.info(
                "an honest confession: we know that referenced resource type "
                "must be ´{path_._where.value}´"
                "but don`t have any restriction implementation yet! "
                "It`s now user end who has to make sure that he is "
                "provided search value that represent appropriate resource type"
            )

        new_path = path_ / "reference"

        return self.create_term(new_path, value, modifier)

    def create_exists_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, tuple):
            operator_, original_value = param_value
            if original_value == "true":
                return exists_(path_)
            elif original_value:
                return not_exists_(path_)

        raise NotImplementedError

    def create_money_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_money_term(path_, value, modifier)
                terms.append(term)
            group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)

            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_money_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_money_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        operator_eq = "eq"
        has_pipe = "|" in original_value
        # modifier = text, no impact
        if has_pipe:
            terms = list()
            parts = original_value.split("|")

            if original_value.startswith("|"):
                new_value = (operator_eq, original_value[1:])
                path_1 = path_ / "currency"
                term = self.create_term(path_1, new_value, modifier)
                terms.append(term)

            elif len(parts) == 2:
                path_1 = path_ / "value"
                new_value = (operator_, parts[0])
                term = self.create_term(path_1, new_value, modifier)
                terms.append(term)

                if parts[1]:
                    # check if val||unit or code
                    path_2 = path_ / "currency"
                    new_value = (operator_eq, parts[1])
                    term = self.create_term(path_2, new_value, modifier)
                    terms.append(term)

            else:
                # may be validation error
                raise NotImplementedError

            if len(terms) > 1:
                return G_(*terms, path=path_, type_=GroupType.COUPLED)
            else:
                return terms[0]
        else:
            path_1 = path_ / "value"
            return self.create_term(path_1, value, modifier)

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

            g_term = G_(*terms, path=path_)
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

        self.validate_normalized_value(param_name_, param_value_, modifier_)

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

    def validate_normalized_value(self, param_name, param_value, modifier):
        """ """
        if modifier in ("missing", "exists"):
            if not isinstance(param_value, tuple):
                raise ValidationError(
                    "Multiple values are not allowed for missing(exists) search"
                )

            if not param_value[1] in ("true", "false"):

                raise ValidationError(
                    "Only ´true´ or ´false´ as value is "
                    "allowed for missing(exists) search"
                )

    def resolve_path_context(self, param_name):
        """ """
        search_param = getattr(self.definition, param_name, None)
        if search_param is None:
            raise ValidationError(
                "No search definition is available for search parameter "
                f"``{param_name}`` on Resource ``{self.context.resource_name}``."
            )

        if search_param.expression is None:
            raise NotImplementedError
        path_ = ElementPath.from_el_path(search_param.expression)
        path_.finalize(self.context.engine)

        return path_

    def attach_sort_terms(self, builder):
        """ """
        terms = list()
        if "_sort" in self.result_params:
            for sort_field in self.result_params["_sort"].split(","):
                order_ = SortOrderType.ASC
                if sort_field.startswith("-"):
                    order_ = SortOrderType.DESC
                    sort_field = sort_field[1:]

                path_ = self.resolve_path_context(sort_field)

                terms.append(sort_(path_, order_))
        if len(terms) > 0:
            return builder.sort(*terms)
        return builder

    def attach_limit_terms(self, builder):
        """ """
        if "_count" not in self.result_params:
            return builder

        offset = 0
        if "page" in self.result_params:
            current_page = self.result_params["page"]
            if current_page > 1:
                offset = (current_page - 1) * self.result_params["_count"]
        return builder.limit(self.result_params["_count"], offset)

    def response(self, result):
        """ """
        return self.context.engine.wrapped_with_bundle(result)

    def __call__(self):
        """ """
        query_result = self.build()
        result = query_result.fetchall()
        response = self.response(result)

        return response


class AsyncSearch(Search):
    """ """

    async def __call__(self):
        """ """
        query_result = self.build()
        result = await query_result.fetchall()
        response = self.response(result)

        return response


@at_least_one_of("query_string", "params")
@mutually_exclusive_parameters("query_string", "params")
def fhir_search(context, query_string=None, params=None):
    """ """
    if context.async_result:
        klass = AsyncSearch
    else:
        klass = Search
    factory = klass(context, query_string=query_string, params=params)
    return factory()
