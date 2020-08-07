# _*_ coding: utf-8 _*_
import logging
import re
from typing import Dict, Pattern, Set, Text
from urllib.parse import unquote_plus

from multidict import MultiDict, MultiDictProxy
from zope.interface import Invalid, implementer

from fhirpath.enums import (
    FHIR_VERSION,
    GroupType,
    MatchType,
    SortOrderType,
    WhereConstraintType,
)
from fhirpath.exceptions import ValidationError
from fhirpath.fql import (
    G_,
    T_,
    V_,
    contains_,
    eb_,
    exists_,
    not_,
    not_exists_,
    sa_,
    sort_,
)
from fhirpath.fql.types import ElementPath
from fhirpath.interfaces import IGroupTerm, ISearch, ISearchContext
from fhirpath.query import Q_
from fhirpath.storage import SEARCH_PARAMETERS_STORAGE

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

escape_comma_replacer: Text = "_ESCAPE_COMMA_"
uri_scheme: Pattern = re.compile(r"^https?://", re.I)
value_prefixes: Set[str] = {"eq", "ne", "gt", "lt", "ge", "le", "sa", "eb", "ap"}
has_dot_as: Pattern = re.compile(r"\.as\([a-z]+\)$", re.I ^ re.U)
has_dot_is: Pattern = re.compile(r"\.is\([a-z]+\)$", re.I ^ re.U)
has_dot_where: Pattern = re.compile(r"\.where\([a-z\=\'\"()]+\)", re.I ^ re.U)
parentheses_wrapped: Pattern = re.compile(r"^\(.+\)$")
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

    def __init__(self, context: SearchContext, query_string=None, params=None):
        """ """
        # validate first
        Search.validate_params(context, query_string, params)

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

        self.result_params: Dict = dict()
        self.search_params = None

        self.prepare_params(all_params)

        self.definition = Search.get_parameter_definition(
            self.context.engine.fhir_release, self.context.resource_name
        )

    @staticmethod
    def validate_params(context, query_string, params):
        """ """
        if not ISearchContext.providedBy(context):
            raise ValidationError(
                ":context must be implemented "
                "fhirpath.interfaces.ISearchContext interface"
            )

        if query_string is None and params is None:
            raise ValidationError(
                "At least one of value is required, "
                "either ´query_string´ or search ´params´ "
            )
        if query_string and params:
            raise ValidationError(
                "Only value from one of arguments "
                "(´query_string´, ´params´) is accepted"
            )

    def prepare_params(self, all_params):
        """making search, sort, limit, params
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

        return params

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
        fhir_release = FHIR_VERSION.normalize(fhir_release)
        storage = SEARCH_PARAMETERS_STORAGE.get(fhir_release.name)

        if storage.empty():
            """Need to load first """
            from fhirpath.fhirspec import FHIRSearchSpecFactory

            spec = FHIRSearchSpecFactory.from_release(fhir_release.name)
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
            if isinstance(normalized_data, tuple):
                normalized_data = [normalized_data]
            for nd in normalized_data:
                self.add_term(nd, terms_container)

        factory = self.attach_limit_terms(
            self.attach_sort_terms(builder.where(*terms_container))
        )

        result = factory(
            unrestricted=self.context.unrestricted,
            async_result=self.context.async_result,
        )
        return result

    def add_term(self, normalized_data, terms_container):
        """ """
        if isinstance(normalized_data, list):
            if len(normalized_data) > 1:
                terms = list()
                for nd in normalized_data:
                    self.add_term(nd, terms)
                return G_(*terms, path=None, type_=GroupType.DECOUPLED)

            else:
                normalized_data = normalized_data[0]

        path_, param_value, modifier = normalized_data

        if path_._where is not None:
            if path_._where.type == WhereConstraintType.T3:
                # we know what to do
                raise NotImplementedError
        elif path_._is is not None:
            raise NotImplementedError

        if modifier in ("missing", "exists"):
            term = self.create_exists_term(path_, param_value, modifier)

        elif (
            getattr(path_.context.type_class, "is_primitive", None)
            and not path_.context.type_class.is_primitive()
        ):
            # we need normalization
            klass_name = path_.context.type_class.fhir_type_name()
            if klass_name == "Reference":
                path_ = path_ / "reference"
                term_factory = self.create_term
            elif klass_name == "Identifier":
                term_factory = self.create_identifier_term
            elif klass_name in ("Quantity", "Duration"):
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
            group = G_(*terms, path=path_, type_=GroupType.COUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_identifier_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_identifier_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        if isinstance(original_value, list):
            terms_ = list()
            for val in original_value:
                term_ = self.single_valued_identifier_term(path_, val, modifier)
                terms_.append(term_)
            # IN Like Group
            group = G_(*terms_, path=path_, type_=GroupType.DECOUPLED)
            return group

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
            group = G_(*terms, path=path_, type_=GroupType.COUPLED)

            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_quantity_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_quantity_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms_ = list()
            for val in original_value:
                term_ = self.single_valued_quantity_term(path_, val, modifier)
                terms_.append(term_)
            # IN Like Group
            group = G_(*terms_, path=path_, type_=GroupType.DECOUPLED)
            return group

        operator_eq = "eq"
        has_pipe = "|" in original_value
        # modifier = text, no impact
        if has_pipe:
            terms = list()
            parts = original_value.split("|")

            if len(parts) == 3:
                if parts[0]:
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

            elif len(parts) == 2:
                if parts[0]:
                    path_1 = path_ / "value"
                    new_value = (operator_, parts[0])
                    term = self.create_term(path_1, new_value, modifier)
                    terms.append(term)

                if parts[1]:
                    path_2 = path_ / "unit"
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

    def create_coding_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_coding_term(path_, value, modifier)
                terms.append(term)
            group = G_(*terms, path=path_, type_=GroupType.COUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_coding_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_coding_term(
        self, path_, value, modifier, ignore_not_modifier=False
    ):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms_ = list()
            for val in original_value:
                term_ = self.single_valued_coding_term(path_, val, modifier)
                terms_.append(term_)
            # IN Like Group
            group = G_(*terms_, path=path_, type_=GroupType.DECOUPLED)
            return group

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

        group = G_(*terms, path=path_, type_=GroupType.COUPLED)
        if modifier == "not" and ignore_not_modifier is False:
            group.match_operator = MatchType.NONE
        return group

    def create_codeableconcept_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_codeableconcept_term(path_, value, modifier)
                terms.append(term)
            group = G_(*terms, path=path_, type_=GroupType.COUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_codeableconcept_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_codeableconcept_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms_ = list()
            for val in original_value:
                term_ = self.single_valued_codeableconcept_term(path_, val, modifier)
                if IGroupTerm.providedBy(term_):
                    if term_.match_operator == MatchType.NONE:
                        # important!
                        term_.match_operator = None
                terms_.append(term_)
            # IN Like Group
            group = G_(*terms_, path=path_, type_=GroupType.DECOUPLED)
            if modifier == "not":
                group.match_operator = MatchType.NONE
            return group

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
            group = G_(*terms, path=path_, type_=GroupType.COUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_address_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_address_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        if isinstance(original_value, list):
            terms_ = list()
            for val in original_value:
                term_ = self.single_valued_address_term(path_, val, modifier)
                terms_.append(term_)
            # IN Like Group
            group = G_(*terms_, path=path_, type_=GroupType.DECOUPLED)
            return group

        if modifier == "text":
            return self.create_term(path_ / "text", value, None)

        terms = [
            self.create_term(path_ / "text", value, None),
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
            group = G_(*terms, path=path_, type_=GroupType.COUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_contactpoint_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_contactpoint_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms_ = list()
            for val in original_value:
                term_ = self.single_valued_contactpoint_term(path_, val, modifier)
                terms_.append(term_)
            # IN Like Group
            group = G_(*terms_, path=path_, type_=GroupType.DECOUPLED)
            return group

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
            group = G_(*terms, path=path_, type_=GroupType.COUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_humanname_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_humanname_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms_ = list()
            for val in original_value:
                term_ = self.single_valued_humanname_term(path_, val, modifier)
                terms_.append(term_)
            # IN Like Group
            group = G_(*terms_, path=path_, type_=GroupType.DECOUPLED)
            return group

        if modifier == "text":
            return self.create_term(path_ / "text", value, None)

        terms = [
            self.create_term(path_ / "text", value, None),
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
            group = G_(*terms, path=path_, type_=GroupType.COUPLED)
            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_reference_term(path_, param_value, modifier)

    def single_valued_reference_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms_ = list()
            for val in original_value:
                term_ = self.single_valued_reference_term(path_, val, modifier)
                terms_.append(term_)
            # IN Like Group
            group = G_(*terms_, path=path_, type_=GroupType.DECOUPLED)
            return group

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
            if (original_value == "true" and modifier == "exists") or (
                original_value == "false" and modifier == "missing"
            ):
                return exists_(path_)
            elif (original_value == "true" and modifier == "missing") or (
                original_value == "false" and modifier == "exists"
            ):
                return not_exists_(path_)

            raise NotImplementedError

        raise NotImplementedError

    def create_money_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = list()
            for value in param_value:
                # Term or Group
                term = self.create_money_term(path_, value, modifier)
                terms.append(term)
            group = G_(*terms, path=path_, type_=GroupType.COUPLED)

            return group

        elif isinstance(param_value, tuple):
            return self.single_valued_money_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_money_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms_ = list()
            for val in original_value:
                term_ = self.single_valued_money_term(path_, val, modifier)
                terms_.append(term_)
            # IN Like Group
            group = G_(*terms_, path=path_, type_=GroupType.DECOUPLED)
            return group

        if self.context.engine.fhir_release == FHIR_VERSION.STU3:
            # make legacy
            return self._single_valued_money_term_stu3(path_, value, modifier)

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

    def _single_valued_money_term_stu3(self, path_, value, modifier):
        """ """
        assert self.context.engine.fhir_release == FHIR_VERSION.STU3
        return self.single_valued_quantity_term(path_, value, modifier)

    def validate_pre_term(self, operator_, path_, value, modifier):
        """ """
        if modifier in ("above", "below") and operator_ in ("sa", "eb"):
            raise ValidationError(
                "You cannot use modifier (above,below) and prefix (sa,eb) at a time"
            )
        if modifier == "contains" and operator_ != "eq":
            raise NotImplementedError(
                "In case of :contains modifier, only eq prefix is supported"
            )

    def create_term(self, path_, value, modifier):
        """ """
        assert path_.context.type_class is bool or (
            getattr(path_.context.type_class, "is_primitive", None)
            and path_.context.type_class.is_primitive() is True
        )

        if isinstance(value, tuple):
            operator_, original_value = value
            # do validate first
            self.validate_pre_term(operator_, path_, value, modifier)
            if isinstance(original_value, list):
                # we force IN will have equal or not equal operator_
                # xxx: should be validated already
                terms_ = list()
                for val in original_value:
                    term_ = self.create_term(path_, val, modifier)
                    terms_.append(term_)
                # IN Like Group
                group = G_(*terms_, path=path_, type_=GroupType.DECOUPLED)
                return group

            term = T_(path_)
            if modifier == "not":
                term = not_(term)
            elif modifier == "below" and operator_ == "eq":
                operator_ = "sa"
            elif modifier == "above" and operator_ == "eq":
                operator_ = "eb"

            val = V_(original_value)

            if operator_ == "eq":
                if modifier == "contains":
                    term = contains_(term, val)
                else:
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
            elif operator_ == "sa":
                term = sa_(term, val)
            elif operator_ == "eb":
                term = eb_(term, val)
            else:
                raise NotImplementedError

            return term

        elif isinstance(value, list):
            # Group Term
            terms = list()
            for val in value:
                term = self.create_term(path_, val, modifier)
                terms.append(term)

            g_term = G_(*terms, path=path_, type_=GroupType.COUPLED)
            return g_term

    def normalize_param_value(self, raw_value, container):
        """ """
        if isinstance(raw_value, list):
            bucket = list()
            for rv in raw_value:
                self.normalize_param_value(rv, bucket)
            if len(bucket) == 1:
                container.append(bucket[0])
            else:
                container.append(bucket)

        else:
            escape_ = has_escape_comma(raw_value)
            if escape_:
                param_value = raw_value.replace("\\,", escape_comma_replacer)
            else:
                param_value = raw_value

            value_parts = param_value.split(",")
            comparison_operator = "eq"
            bucket_ = list()
            for val in value_parts:
                if escape_:
                    val_ = val.replace(escape_comma_replacer, "\\,")
                else:
                    val_ = val

                for prefix in value_prefixes:
                    if val_.startswith(prefix):
                        comparison_operator = prefix
                        val_ = val_[2:]
                        break
                bucket_.append((comparison_operator, val_))
            if len(bucket_) == 1:
                container.append(bucket_[0])
            else:
                container.append((None, bucket_))

    def normalize_param(self, param_name):
        """ """
        try:
            parts = param_name.split(":")
            param_name_ = parts[0]
            modifier_ = parts[1]
        except IndexError:
            modifier_ = None
        raw_value = list(self.search_params.getall(param_name, []))
        # Let's look at for any composite or combo type parameter
        search_param = self._get_search_param_definition(param_name_)
        if search_param.type == "composite":
            return self._normalize_composite_param(
                raw_value, param_def=search_param, modifier=modifier_
            )

        if len(raw_value) == 0:
            raw_value = None
        elif len(raw_value) == 1:
            raw_value = raw_value[0]

        values = list()
        self.normalize_param_value(raw_value, values)

        if len(values) == 1:
            param_value_ = values[0]
        else:
            param_value_ = values

        Search.validate_normalized_value(param_name_, param_value_, modifier_)
        _path = self.resolve_path_context(param_name_)
        return _path, param_value_, modifier_

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

    @staticmethod
    def validate_normalized_value(param_name, param_value, modifier):
        """
        :param param_name:
        :param param_value:
        :param modifier:
        """
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
        search_param = self._get_search_param_definition(param_name)

        if search_param.expression is None:
            raise NotImplementedError

        # Some Safegurds
        if search_param.type == "composite":
            raise NotImplementedError

        if search_param.type in ("token", "composite") and search_param.code.startswith(
            "combo-"
        ):
            raise NotImplementedError

        dotted_path = search_param.expression

        if parentheses_wrapped.match(dotted_path):
            dotted_path = dotted_path[1:-1]

        return self._dotted_path_to_path_context(dotted_path)

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

    def _get_search_param_definition(self, param_name):
        """ """
        search_param = getattr(self.definition, param_name, None)
        if search_param is None:
            raise ValidationError(
                "No search definition is available for search parameter "
                f"``{param_name}`` on Resource ``{self.context.resource_name}``."
            )
        return search_param

    def _dotted_path_to_path_context(self, dotted_path):
        """ """
        if len(dotted_path.split(".")) == 1:
            raise ValidationError("Invalid dotted path ´{0}´".format(dotted_path))

        path_ = ElementPath.from_el_path(dotted_path)
        path_.finalize(self.context.engine)

        return path_

    def _normalize_composite_param(self, raw_value, param_def, modifier):
        """ """
        if len(raw_value) < 1:
            raise NotImplementedError(
                "Currently duplicate composite type "
                "params are not allowed or supported"
            )
        value_parts = raw_value[0].split("&")
        assert len(value_parts) == 2

        composite_bucket = list()

        part1 = [
            ".".join([param_def.expression, param_def.component[0]["expression"]]),
            value_parts[0],
        ]
        part1_param_value = list()
        self.normalize_param_value(part1[1], part1_param_value)
        if len(part1_param_value) == 1:
            part1_param_value = part1_param_value[0]
        composite_bucket.append(
            (self._dotted_path_to_path_context(part1[0]), part1_param_value, modifier)
        )
        part2 = list()
        for expr in param_def.component[1]["expression"].split("|"):
            part_ = [".".join([param_def.expression, expr.strip()]), value_parts[1]]
            part2.append(part_)
        part2_param_value = list()
        self.normalize_param_value(part2[0][1], part2_param_value)

        if len(part2_param_value) == 1:
            part2_param_value = part2_param_value[0]
        part2_temp = list()
        for pr in part2:
            part2_temp.append(
                (self._dotted_path_to_path_context(pr[0]), part2_param_value, modifier)
            )
        if len(part2_temp) == 1:
            part2_temp = part2_temp[0]

        composite_bucket.append(part2_temp)

        return composite_bucket

    def __call__(self):
        """ """
        query_result = self.build()
        result = query_result.fetchall()
        assert result is not None
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


def fhir_search(context, query_string=None, params=None):
    """ """
    if context.async_result:
        klass = AsyncSearch
    else:
        klass = Search
    factory = klass(context, query_string=query_string, params=params)
    return factory()
