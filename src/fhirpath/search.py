# _*_ coding: utf-8 _*_
import logging
import re
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Pattern,
    Set,
    Text,
    Tuple,
    Type,
    Union,
    cast,
)
from urllib.parse import unquote_plus
from warnings import warn

from multidict import MultiDict, MultiDictProxy
from zope.interface import implementer

from fhirpath.engine import EngineResult, EngineResultBody, EngineResultHeader
from fhirpath.enums import (
    FHIR_VERSION,
    GroupType,
    MatchType,
    SortOrderType,
    WhereConstraintType,
)
from fhirpath.exceptions import ValidationError
from fhirpath.fhirspec import (
    FHIRSearchSpecFactory,
    ResourceSearchParameterDefinition,
    SearchParameter,
    lookup_fhir_resource_spec,
    search_param_prefixes,
)
from fhirpath.fql import (
    G_,
    T_,
    V_,
    contains_,
    eb_,
    exact_,
    exists_,
    not_,
    not_exists_,
    sa_,
    sort_,
)
from fhirpath.fql.types import ElementPath
from fhirpath.interfaces import IGroupTerm, ISearch, ISearchContext
from fhirpath.query import Q_, QueryResult
from fhirpath.storage import SEARCH_PARAMETERS_STORAGE

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

escape_comma_replacer: Text = "_ESCAPE_COMMA_"
uri_scheme: Pattern = re.compile(r"^https?://", re.I)
value_prefixes: Set[str] = {"eq", "ne", "gt", "lt", "ge", "le", "sa", "eb", "ap"}
has_dot_as: Pattern = re.compile(r"\.as\([a-z]+\)$", re.I ^ re.U)
has_dot_is: Pattern = re.compile(r"\.is\([a-z]+\)$", re.I ^ re.U)
has_dot_where: Pattern = re.compile(r"\.where\([a-z=\'\"()]+\)", re.I ^ re.U)
parentheses_wrapped: Pattern = re.compile(r"^\(.+\)$")
logger = logging.getLogger("fhirpath.search")

DEFAULT_RESULT_COUNT = 100


def has_escape_comma(val):
    return "\\," in val


@implementer(ISearchContext)
class SearchContext(object):
    """ """

    __slots__ = (
        "resource_types",
        "engine",
        "unrestricted",
        "async_result",
        "definitions",
        "search_params_intersection",
    )

    definitions: List[ResourceSearchParameterDefinition]

    def __init__(self, engine, resource_type, unrestricted=False, async_result=None):
        """ """
        self.engine = engine
        self.resource_types = [resource_type] if resource_type else []
        self.unrestricted = unrestricted
        self.async_result = self.engine.__class__.is_async()
        if async_result is not None:
            warn(
                "'async_result' is no longer used, as Engine has that info already. "
                "this parameter will be removed in future release.",
                category=DeprecationWarning,
            )

        self.definitions = self.get_parameters_definition(self.engine.fhir_release)

    def get_parameters_definition(
        self,
        fhir_release: FHIR_VERSION,
    ) -> List[ResourceSearchParameterDefinition]:
        """ """
        fhir_release = FHIR_VERSION.normalize(fhir_release)
        storage = SEARCH_PARAMETERS_STORAGE.get(fhir_release.name)

        if storage.empty():
            spec = FHIRSearchSpecFactory.from_release(fhir_release.name)
            spec.write()

        # if self.resource_types is empty, return the searchparams
        # definitions of the generic "Resource" type.
        return [
            storage.get(resource_type)
            for resource_type in (self.resource_types or ["Resource"])
        ]

    def augment_with_types(self, resource_types: List[str]):
        if len(resource_types) == 0:
            return

        self.resource_types.extend(resource_types)
        self.definitions = self.get_parameters_definition(self.engine.fhir_release)

        self.search_params_intersection = [
            sp for sp in self.definitions[0] if all(sp in d for d in self.definitions)
        ]

    def resolve_path_context(self, search_param: SearchParameter):
        """ """
        if search_param.expression is None:
            raise NotImplementedError

        # Some Safeguards
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

    def normalize_param(
        self, param_name, raw_value
    ) -> List[Tuple[ElementPath, str, Optional[str]]]:
        """ """
        try:
            parts = param_name.split(":")
            param_name_ = parts[0]
            modifier_ = parts[1]
        except IndexError:
            modifier_ = None

        normalized_params: List[Tuple[ElementPath, str, Optional[str]]] = []
        search_params_def = self._get_search_param_definitions(param_name_)

        for sp in search_params_def:
            # Look out for any composite or combo type parameter
            if sp.type == "composite":
                normalized_params.extend(
                    self._normalize_composite_param(
                        raw_value, param_def=sp, modifier=modifier_
                    )
                )
                continue

            if len(raw_value) == 0:
                raw_value = None
            elif len(raw_value) == 1:
                raw_value = raw_value[0]

            values: List = self.normalize_param_value(raw_value, sp)

            if len(values) == 0:
                # empty parameters are not considered an error, they should be ignored
                continue
            if len(values) == 1:
                param_value_ = values[0]
            else:
                param_value_ = values

            Search.validate_normalized_value(param_name_, param_value_, modifier_)
            _path = self.resolve_path_context(sp)
            normalized_params.append((_path, param_value_, modifier_))
        return normalized_params

    def normalize_param_value(
        self, raw_value: Union[List, str], search_param: SearchParameter
    ):
        normalized_values: List[Any] = []
        if not raw_value:
            return []

        elif isinstance(raw_value, list):
            bucket: List[str] = list()
            for rv in raw_value:
                bucket.extend(self.normalize_param_value(rv, search_param))
            if len(bucket) == 1:
                normalized_values.append(bucket[0])
            else:
                normalized_values.append(bucket)

        else:
            escape_ = has_escape_comma(raw_value)
            if escape_:
                param_value = raw_value.replace("\\,", escape_comma_replacer)
            else:
                param_value = raw_value

            value_parts = param_value.split(",")
            bucket_ = list()
            for val in value_parts:
                comparison_operator = "eq"
                if escape_:
                    val_ = val.replace(escape_comma_replacer, "\\,")
                else:
                    val_ = val

                for prefix in search_param_prefixes:
                    if val_.startswith(prefix) and search_param.support_prefix():
                        comparison_operator = prefix
                        val_ = val_[2:]
                        break
                bucket_.append((comparison_operator, val_))
            if len(bucket_) == 1:
                normalized_values.append(bucket_[0])
            else:
                normalized_values.append((None, bucket_))

        return normalized_values

    def _get_search_param_definitions(self, param_name) -> List[SearchParameter]:
        """ """
        params_def = []
        for definition in self.definitions:
            search_param = getattr(definition, param_name, None)
            if search_param is None:
                if param_name in ("_format", "_pretty"):
                    continue
                raise ValidationError(
                    "No search definition is available for search parameter "
                    f"``{param_name}`` on Resource ``{definition.resource_type}``."
                )
            params_def.append(search_param)
        return params_def

    def _dotted_path_to_path_context(self, dotted_path):
        """ """
        if len(dotted_path.split(".")) == 1:
            raise ValidationError("Invalid dotted path ´{0}´".format(dotted_path))

        path_ = ElementPath.from_el_path(dotted_path)
        path_.finalize(self.engine)
        return path_

    def _normalize_composite_param(
        self, raw_value, param_def, modifier
    ) -> List[Tuple[ElementPath, str, Optional[str]]]:
        """ """
        if len(raw_value) < 1:
            raise NotImplementedError(
                "Currently duplicate composite type params are not allowed or supported"
            )
        value_parts = raw_value[0].split("$")
        if len(value_parts) != len(param_def.component):
            raise ValueError(
                f"Composite search param {param_def.name} expects {len(param_def.component)} "
                f"values separated by a '$', got {len(value_parts)}."
            )

        results: List[Tuple[ElementPath, str, Optional[str]]] = [
            self.parse_composite_parameter_component(
                component, value_part, param_def, modifier
            )
            for component, value_part in zip(param_def.component, value_parts)
        ]
        return results

    def parse_composite_parameter_component(
        self, component, raw_value, param_def, modifier
    ):
        result = []
        for expr in component["expression"].split("|"):
            component_dotted_path = ".".join([param_def.expression, expr.strip()])

            component_param_value = self.normalize_param_value(raw_value, param_def)
            if len(component_param_value) == 1:
                component_param_value = component_param_value[0]

            result.append(
                (
                    self._dotted_path_to_path_context(component_dotted_path),
                    component_param_value,
                    modifier,
                )
            )

        if len(result) == 1:
            return result[0]
        return result


@implementer(ISearch)
class Search(object):
    """ """

    def __init__(self, context: SearchContext, query_string=None, params=None):
        """ """
        # validate first
        Search.validate_params(context, query_string, params)

        self.context = ISearchContext(context)
        all_params = None
        if isinstance(params, MultiDict):
            all_params = params
        elif isinstance(query_string, str):
            all_params = Search.parse_query_string(query_string, False)
        elif isinstance(params, (tuple, list)):
            all_params = MultiDict(params)
        elif isinstance(params, dict):
            all_params = MultiDict(params.items())
        elif isinstance(params, MultiDictProxy):
            all_params = params.copy()

        self.result_params: Dict[str, str] = dict()
        self.search_params = None

        self.reverse_chaining_results: Optional[Dict[str, Set[str]]] = None
        self.main_query = None
        self.include_queries = None

        self.prepare_params(all_params)

        additional_resource_types = self.result_params.get("_type")
        if additional_resource_types:
            self.context.augment_with_types(additional_resource_types)

    @staticmethod
    def validate_params(context, query_string, params):
        """ """
        if not ISearchContext.providedBy(context):
            raise ValidationError(
                ":context must be implemented "
                "fhirpath.interfaces.ISearchContext interface"
            )

        if query_string and params:
            raise ValidationError(
                "Only value from one of arguments "
                "(´query_string´, ´params´) is accepted"
            )

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
        if all_params is None:
            self.search_params = MultiDict()
            return

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

        _type = all_params.popone("_type", None)
        if _type:
            self.result_params["_type"] = _type.split(",")

        _summary = all_params.popone("_summary", None)
        if _summary:
            self.result_params["_summary"] = _summary

        _include = all_params.popall("_include", None)
        if _include:
            self.result_params["_include"] = _include

        _has = [(k, v) for k, v in all_params.items() if k.startswith("_has:")]
        if _has:
            self.result_params["_has"] = _has
        [all_params.pop(k) for k, _ in _has]

        _revinclude = all_params.popall("_revinclude", None)
        if _revinclude:
            self.result_params["_revinclude"] = _revinclude

        _elements = all_params.popone("_elements", [])
        if len(_elements) > 0:
            self.result_params["_elements"] = _elements.split(",")

        _contained = all_params.popone("_contained", None)
        if _contained:
            self.result_params["_contained"] = _contained

        _containedType = all_params.popone("_containedType", None)
        if _containedType:
            self.result_params["_containedType"] = _containedType

        self.search_params = MultiDictProxy(all_params)

    def build(self) -> QueryResult:
        """Create QueryBuilder from search query string"""
        builder = Q_(self.context.resource_types, self.context.engine)

        builder = self.attach_where_terms(builder)
        builder = self.attach_elements_terms(builder)
        builder = self.attach_sort_terms(builder)
        builder = self.attach_summary_terms(builder)
        builder = self.attach_limit_terms(builder)

        # handle _has predicates
        if self.reverse_chaining_results:
            # filter results on IDs
            terms: List = []
            for resource_type, ids in self.reverse_chaining_results.items():
                search_context = SearchContext(self.context.engine, resource_type)
                normalized_data = search_context.normalize_param("_id", ",".join(ids))
                self.add_term(normalized_data, terms)

            builder = builder.where(*terms)

        result: QueryResult = builder(unrestricted=self.context.unrestricted)

        return result

    # FIXME: sorting, paginating and large results are not handled yet.
    def has(self) -> List[Tuple[SearchParameter, QueryResult]]:
        """
        This function handles the _has keyword.
        """
        has_queries: List[Tuple[SearchParameter, QueryResult]] = []
        _has_predicates: List[Tuple[str, str]] = cast(
            List[Tuple[str, str]], self.result_params.get("_has", [])
        )
        for _has, value in _has_predicates:
            # Parse the _has input parameter
            parts = _has.split(":")
            if len(parts) != 4:
                raise ValidationError(
                    f"bad _has param '{_has}', should be "
                    "_has:Resource:ref_search_param:value_search_param=value"
                )

            from_resource_type: str = parts[1]
            ref_param_raw: str = parts[2]
            value_param_raw: str = parts[3]

            from_context = SearchContext(self.context.engine, from_resource_type)

            # Get the reference search parameter definition
            # we use the first definition returned since we
            # only have one resource in the context
            ref_param = from_context._get_search_param_definitions(ref_param_raw)[0]
            if not ref_param:
                raise ValidationError(
                    f"search parameter {from_resource_type}.{ref_param_raw} is unknown"
                )
            if ref_param.type != "reference":
                raise ValidationError(
                    f"search parameter {from_resource_type}.{ref_param_raw} "
                    f"must be of type 'reference', got {ref_param.type}"
                )
            # ensure that the reference search param targets the correct type
            assert isinstance(ref_param.target, list)
            if not any(r in ref_param.target for r in self.context.resource_types):
                raise ValidationError(
                    f"invalid reference {from_resource_type}.{ref_param_raw} "
                    f"({','.join(ref_param.target)}) in the current search context "
                    f"({','.join(self.context.resource_types)})"
                )

            # Get the value search parameter definition
            value_param = from_context._get_search_param_definitions(value_param_raw)[0]
            if not value_param:
                raise ValidationError(
                    f"search parameter {from_resource_type}.{ref_param_raw} is unknown"
                )
            # Build a Q_ (query) object to join the resource based on reference ids.
            builder = Q_(from_resource_type, from_context.engine)
            normalized_data = from_context.normalize_param(value_param_raw, value)
            terms_container: List = []
            self.add_term(normalized_data, terms_container)

            builder = builder.where(*terms_container)
            self.attach_limit_terms(builder)

            result: QueryResult = builder(unrestricted=self.context.unrestricted)
            has_queries.append((ref_param, result))

        return has_queries

    # FIXME: sorting, paginating and large results are not handled yet.
    def include(self, main_query_result: EngineResult) -> List[QueryResult]:
        """
        This function handles the _include keyword.
        """
        include_queries: List[QueryResult] = []
        for inc in self.result_params.get("_include", []):
            # Parse the _include input parameter
            parts = inc.split(":")
            if len(parts) < 2 or len(parts) > 3:
                raise ValidationError(
                    f"bad _include param '{inc}', "
                    "should be Resource:search_param[:target_type]"
                )

            from_resource_type = parts[0]
            ref_param_raw: str = parts[1]
            target_ref_type = parts[2] if len(parts) == 3 else None

            # Get the search parameter definition
            # it must be of type reference
            ref_param: SearchParameter = SearchContext(
                self.context.engine, from_resource_type
            )._get_search_param_definitions(ref_param_raw)[0]
            if not ref_param:
                raise ValidationError(
                    f"search parameter {from_resource_type}.{ref_param_raw} is unknown"
                )
            if ref_param.type != "reference":
                raise ValidationError(
                    f"search parameter {from_resource_type}.{ref_param_raw} "
                    f"must be of type 'reference', got {ref_param.type}"
                )
            assert isinstance(ref_param.target, list)
            if target_ref_type and target_ref_type not in ref_param.target:
                raise ValidationError(
                    f"the search param {from_resource_type}.{ref_param_raw} may refer"
                    f" to {', '.join(ref_param.target)}, not to {target_ref_type}"
                )

            # Compute the resources which may be included in the join query
            included_resources = (
                [target_ref_type] if target_ref_type else ref_param.target
            )

            # Extract reference IDs from the main query result
            ids = main_query_result.extract_references(ref_param)

            # filter included resources for which we have references to
            included_resources = [r for r in included_resources if ids.get(r)]

            # if no references were extracted from the main_query_result, skip.
            if not included_resources:
                continue

            # Build a Q_ (query) object to join the resource based on reference ids.
            builder = Q_(included_resources, self.context.engine)
            terms: List = []
            for resource_type in included_resources:
                search_context = SearchContext(self.context.engine, resource_type)
                # for each resource, create a term to filter IDs
                normalized_data = search_context.normalize_param(
                    "_id", ",".join(ids[resource_type])
                )
                self.add_term(normalized_data, terms)

            builder = builder.where(*terms)
            self.attach_limit_terms(builder)

            # FIXME: find a better way to handle the limit
            builder = builder.limit(DEFAULT_RESULT_COUNT)

            result: QueryResult = builder(unrestricted=self.context.unrestricted)
            include_queries.append(result)

        return include_queries

    # FIXME: sorting, paginating and large results are not handled yet.
    def rev_include(self, main_query_result: EngineResult) -> List[QueryResult]:
        """
        This function handles the _revinclude keyword.
        """
        include_queries: List[QueryResult] = []
        for inc in self.result_params.get("_revinclude", []):
            # Parse the _revinclude input parameter
            parts = inc.split(":")
            if len(parts) < 2 or len(parts) > 3:
                raise ValidationError(
                    f"bad _revinclude param '{inc}', "
                    "should be Resource:search_param[:target_type]"
                )

            from_resource_type = parts[0]
            ref_param_raw: str = parts[1]
            target_ref_type = parts[2] if len(parts) == 3 else None

            # Get the search parameter definition
            # it must be of type reference
            ref_param: SearchParameter = SearchContext(
                self.context.engine, from_resource_type
            )._get_search_param_definitions(ref_param_raw)[0]
            if not ref_param:
                raise ValidationError(
                    f"search parameter {from_resource_type}.{ref_param_raw} is unknown"
                )
            if ref_param.type != "reference":
                raise ValidationError(
                    f"search parameter {from_resource_type}.{ref_param_raw} "
                    f"must be of type 'reference', got {ref_param.type}"
                )
            assert isinstance(ref_param.target, list)
            if target_ref_type and target_ref_type not in ref_param.target:
                raise ValidationError(
                    f"invalid reference {from_resource_type}.{ref_param_raw} "
                    f"({','.join(ref_param.target)}) in the current search context "
                    f"({','.join(self.context.resource_types)})"
                )

            # Extract IDs from the main query result
            ids = main_query_result.extract_ids()

            # if no IDs were extracted from the main_query_result, skip.
            if not ids:
                continue

            # Build a Q_ (query) object to join the resource based on reference ids.
            builder = Q_([from_resource_type], self.context.engine)
            terms: List = []
            for _, resource_ids in ids.items():
                search_context = SearchContext(self.context.engine, from_resource_type)
                # for each resource, create a term to filter reference ids
                normalized_data = search_context.normalize_param(
                    ref_param_raw, ",".join(resource_ids)
                )
                self.add_term(normalized_data, terms)

            builder = builder.where(*terms)
            self.attach_limit_terms(builder)

            result: QueryResult = builder(unrestricted=self.context.unrestricted)
            include_queries.append(result)

        return include_queries

    def add_term(self, normalized_data, terms_container):
        """ """
        if isinstance(normalized_data, list):
            if len(normalized_data) > 1:
                terms = list()
                for nd in normalized_data:
                    self.add_term(nd, terms)
                # I think we'll be there only in the case of composite search params
                # The Group path is only needed to build nested queries so using
                # whichever component path should be ok.
                # This could still use a refacto though...
                group_term = G_(*terms, path=nd[0], type_=GroupType.COUPLED)
                terms_container.append(group_term)
                return group_term

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
            hasattr(path_.context.type_class, "is_primitive")
            and not path_.context.type_class.is_primitive()
        ):
            # we need normalization
            klass_name = path_.context.type_class.fhir_type_name()
            if klass_name == "Reference":
                if modifier == "identifier":
                    path_ = path_ / "identifier"
                    term_factory = self.create_identifier_term
                else:
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
            elif klass_name == "Period":
                term_factory = self.create_period_term
            else:
                raise NotImplementedError(
                    f"Can't perform search on element of type {klass_name}"
                )
            term = term_factory(path_, param_value, modifier)
        else:
            term = self.create_term(path_, param_value, modifier)
        if isinstance(term, list):
            terms_container.extend(term)
        else:
            terms_container.append(term)

    def create_identifier_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = [
                self.create_identifier_term(path_, value, modifier)
                for value in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_identifier_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_identifier_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        if isinstance(original_value, list):
            terms = [
                self.single_valued_identifier_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group

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
            terms = [
                self.create_quantity_term(path_, value, modifier)
                for value in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_quantity_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_quantity_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_quantity_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group

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
            terms = [
                self.create_coding_term(path_, value, modifier) for value in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_coding_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_coding_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_coding_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group

        has_pipe = "|" in original_value
        terms = list()
        subpredicate_modifier = None if modifier == "not" else modifier

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

                term = self.create_term(path_1, new_value, subpredicate_modifier)
                terms.append(term)

            elif original_value.endswith("|"):
                path_1 = path_ / "system"
                new_value = (value[0], original_value[:-1])

                terms.append(self.create_term(path_1, new_value, subpredicate_modifier))

            else:
                parts = original_value.split("|")
                terms = list()
                try:
                    path_1 = path_ / "system"
                    new_value = (value[0], parts[0])
                    term = self.create_term(path_1, new_value, subpredicate_modifier)
                    terms.append(term)

                    path_2 = path_ / "code"
                    new_value = (value[0], parts[1])
                    term = self.create_term(path_2, new_value, subpredicate_modifier)
                    terms.append(term)

                except IndexError:
                    pass
        else:
            path_1 = path_ / "code"
            terms.append(self.create_term(path_1, value, subpredicate_modifier))

        group = G_(*terms, path=path_, type_=GroupType.COUPLED)
        if modifier == "not":
            group.match_operator = MatchType.NONE
        return group

    def create_codeableconcept_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = [
                self.create_codeableconcept_term(path_, value, modifier)
                for value in param_value
            ]
            return terms

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
            terms = [
                self.create_address_term(path_, val, modifier) for val in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_address_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_address_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value
        if isinstance(original_value, list):
            terms = [
                self.single_valued_address_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group

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
            terms = [
                self.create_contactpoint_term(path_, val, modifier)
                for val in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_contactpoint_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_contactpoint_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_contactpoint_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group

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
            group = G_(*terms, path=path_, type_=GroupType.COUPLED)  # Term or Group
        else:
            terms = [
                self.create_term(path_ / "system", value, None),
                self.create_term(path_ / "use", value, None),
                self.create_term(path_ / "value", value, None),
            ]
            group = G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group
        if modifier == "not":
            group.match_operator = MatchType.NONE
        else:
            group.match_operator = MatchType.ANY

        return group

    def create_humanname_term(self, path_, param_value, modifier):
        """ """
        if isinstance(param_value, list):
            terms = [
                self.create_humanname_term(path_, val, modifier) for val in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_humanname_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_humanname_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_humanname_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)  # IN Like Group

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
            terms = [
                self.create_reference_term(path_, value, modifier)
                for value in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_reference_term(path_, param_value, modifier)

    def single_valued_reference_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_reference_term(path_, val, modifier)
                for val in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)

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
            terms = [
                self.create_money_term(path_, value, modifier) for value in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_money_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_money_term(self, path_, value, modifier):
        """ """
        operator_, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_money_term(path_, value, modifier)
                for value in original_value
            ]
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)

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

    def create_period_term(self, path_, param_value, modifier):
        if isinstance(param_value, list):
            terms = [
                self.single_valued_period_term(path_, value, modifier)
                for value in param_value
            ]
            return terms

        elif isinstance(param_value, tuple):
            return self.single_valued_period_term(path_, param_value, modifier)

        raise NotImplementedError

    def single_valued_period_term(self, path_, value, modifier):
        operator, original_value = value

        if isinstance(original_value, list):
            terms = [
                self.single_valued_period_term(path_, val, modifier)
                for val in original_value
            ]
            # IN Like Group
            return G_(*terms, path=path_, type_=GroupType.DECOUPLED)

        if operator == "eq":
            terms = [
                self.create_term(path_ / "start", ("ge", original_value), modifier),
                self.create_term(path_ / "end", ("le", original_value), modifier),
            ]
            type_ = GroupType.COUPLED
        elif operator == "ne":
            terms = [
                self.create_term(path_ / "start", ("lt", original_value), modifier),
                self.create_term(path_ / "end", ("gt", original_value), modifier),
                not_exists_(path_ / "start"),
                not_exists_(path_ / "end"),
            ]
            type_ = GroupType.DECOUPLED
        elif operator == "gt":
            terms = [
                self.create_term(path_ / "end", ("gt", original_value), modifier),
                not_exists_(path_ / "end"),
            ]
            type_ = GroupType.DECOUPLED
        elif operator == "lt":
            terms = [
                self.create_term(path_ / "start", ("lt", original_value), modifier),
            ]
            type_ = GroupType.COUPLED
        elif operator == "ge":
            terms = [
                self.create_term(path_ / "end", ("ge", original_value), modifier),
                not_exists_(path_ / "end"),
            ]
            type_ = GroupType.DECOUPLED
        elif operator == "le":
            terms = [
                self.create_term(path_ / "start", ("le", original_value), modifier),
            ]
            type_ = GroupType.COUPLED
        elif operator == "sa":
            terms = [
                self.create_term(path_ / "start", ("gt", original_value), modifier),
            ]
            type_ = GroupType.COUPLED
        elif operator == "eb":
            terms = [
                self.create_term(path_ / "end", ("lt", original_value), modifier),
            ]
            type_ = GroupType.COUPLED
        elif operator == "ap":
            start_terms = [
                self.create_term(path_ / "start", ("le", original_value), modifier)
            ]
            start_group = G_(*start_terms, path=path_, type_=GroupType.COUPLED)
            end_terms = [
                self.create_term(path_ / "end", ("ge", original_value), modifier),
                not_exists_(path_ / "end"),
            ]
            end_group = G_(*end_terms, path=path_, type_=GroupType.DECOUPLED)
            terms = [start_group, end_group]
            type_ = GroupType.COUPLED
        else:
            raise NotImplementedError(f"prefix {operator} not handled for periods.")

        return G_(*terms, path=path_, type_=type_)

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
                    subpredicate_modifier = None if modifier == "not" else modifier
                    term_ = self.create_term(path_, val, subpredicate_modifier)
                    terms_.append(term_)
                # IN Like Group
                group = G_(*terms_, path=path_, type_=GroupType.DECOUPLED)
                if modifier == "not":
                    return group.match_no_one()
                else:
                    return group.match_any()

            term = T_(path_)
            if modifier == "not":
                term = not_(term)
            elif modifier == "below" and operator_ == "eq":
                operator_ = "sa"
            elif modifier == "above" and operator_ == "eq":
                operator_ = "eb"
            elif modifier == "exact":
                term = exact_(term)
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

    def validate(self):
        """ """
        errors = set()

        for search_param in self.search_params:

            param_name = search_param.split(":")[0]
            try:
                self.context._get_search_param_definitions(param_name)
            except ValidationError as e:
                errors.add(str(e))

        if len(errors) > 0:
            raise ValidationError(", ".join([e for e in errors]))
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

    def attach_where_terms(self, builder):
        terms_container = list()
        # we make sure that there are no duplicate keys!
        for param_name in set(self.search_params):
            raw_value = list(self.search_params.getall(param_name, []))
            normalized_params = self.context.normalize_param(param_name, raw_value)
            for np in normalized_params:
                self.add_term(np, terms_container)

        return builder.where(*terms_container)

    def attach_sort_terms(self, builder):
        """ """
        terms = list()
        if "_sort" in self.result_params:
            for sort_field in self.result_params["_sort"].split(","):
                order_ = SortOrderType.ASC
                if sort_field.startswith("-"):
                    order_ = SortOrderType.DESC
                    sort_field = sort_field[1:]
                for sort_param_def in self.context._get_search_param_definitions(
                    sort_field
                ):
                    path_ = self.context.resolve_path_context(sort_param_def)
                    terms.append(sort_(path_, order_))

        if len(terms) > 0:
            return builder.sort(*terms)
        return builder

    def attach_limit_terms(self, builder):
        """ """
        if "_count" not in self.result_params:
            return builder.limit(DEFAULT_RESULT_COUNT)

        offset = 0
        if "page" in self.result_params:
            current_page = self.result_params["page"]
            if current_page > 1:
                offset = (current_page - 1) * self.result_params["_count"]
        return builder.limit(self.result_params["_count"], offset)

    def attach_elements_terms(self, builder):
        """ """
        if "_elements" not in self.result_params:
            return builder

        paths = [
            f"{r}.{el}"
            for el in self.result_params["_elements"]
            for r in self.context.resource_types
        ]
        mandatories = [
            f"{r}.{el}" for el in ["id"] for r in self.context.resource_types
        ]
        return builder.element(*paths, *mandatories)

    def attach_summary_terms(self, builder):
        """ """
        if "_summary" not in self.result_params:
            return builder

        if self.result_params["_summary"] in ["count", "false"]:
            return builder

        specs = [
            lookup_fhir_resource_spec(r, True, self.context.engine.fhir_release)
            for r in self.context.resource_types
        ]

        if self.result_params["_summary"] in ("data", "true"):

            summary_elements = [
                f"{r}.{attr}"
                for r in self.context.resource_types
                for attr in ["id", "meta"]
            ]

            def should_include(attr):
                if self.result_params["_summary"] == "data":
                    return (
                        not attr.path.endswith(".text")
                        and not attr.is_main_profile_element
                    )
                elif self.result_params["_summary"] == "true":
                    return attr.is_summary

            # filter all summary attributes
            summary_attributes = [
                attr for spec in specs for attr in spec.elements if should_include(attr)
            ]

            def get_attr_paths(attribute):
                if attribute.path.endswith("[x]"):
                    for prop in attribute.as_properties():
                        return [
                            f"{prop.path.rsplit('.', 1)[0]}.{prop.name}"
                            for prop in attribute.as_properties()
                        ]
                else:
                    return [attribute.path]

            # append summary attributes' paths to summary_elements
            summary_elements.extend(
                [path for attr in summary_attributes for path in get_attr_paths(attr)]
            )

            return builder.element(*summary_elements)

        if self.result_params["_summary"] == "text":
            text_elements = [
                el.path
                for spec in specs
                for el in spec.elements
                if el.n_min is not None and el.n_min > 0
            ]
            text_elements.extend(
                [
                    f"{r}.{attr}"
                    for r in self.context.resource_types
                    for attr in ["text", "id", "meta"]
                ]
            )

            return builder.element(*text_elements)

    def response(self, result, includes, as_json):
        """ """
        return self.context.engine.wrapped_with_bundle(
            result, includes=includes, as_json=as_json
        )

    def __call__(self, as_json=False):
        """ """

        # TODO: chaining

        # reverse chaining (_has)
        if self.result_params.get("_has"):
            has_queries = self.has()
            # compute the intersection of referenced resources' ID
            # from the result of _has queries.
            self.reverse_chaining_results = {}
            for ref_param, q in has_queries:
                res = q.fetchall()
                self.reverse_chaining_results = {
                    r_type: set(ids).intersection(self.reverse_chaining_results[r_type])
                    if self.reverse_chaining_results.get(r_type)
                    else set(ids)
                    for r_type, ids in res.extract_references(ref_param).items()
                    if r_type in self.context.resource_types
                }

            # if the _has predicates did not match any documents, return an empty result
            # FIXME: we use the result of the last _has query to build the empty bundle,
            # but we should be more explicit about the query context.
            if not self.reverse_chaining_results:
                return self.response(
                    EngineResult(EngineResultHeader(total=0), EngineResultBody()),
                    [],
                    as_json,
                )

        # MAIN QUERY
        self.main_query = self.build()

        # TODO handle count with _includes
        if self.result_params.get("_summary") == "count":
            main_result = self.main_query.count_raw()
        else:
            main_result = self.main_query.fetchall()
        assert main_result is not None

        # _include
        self.include_queries = self.include(main_result)
        include_results: List[EngineResult] = [
            q.fetchall() for q in self.include_queries
        ]

        # _revinclude
        self.rev_include_queries = self.rev_include(main_result)
        rev_include_results: List[EngineResult] = [
            q.fetchall() for q in self.rev_include_queries
        ]

        all_includes = [*include_results, *rev_include_results]
        return self.response(main_result, all_includes, as_json)


class AsyncSearch(Search):
    """ """

    async def __call__(self, as_json=False):
        """ """
        # TODO: chaining

        # reverse chaining (_has)
        if self.result_params.get("_has"):
            has_queries = self.has()
            # compute the intersection of referenced resources' ID
            # from the result of _has queries.
            self.reverse_chaining_results = {}
            for ref_param, q in has_queries:
                res = await q.fetchall()
                self.reverse_chaining_results = {
                    r_type: set(ids).intersection(self.reverse_chaining_results[r_type])
                    if self.reverse_chaining_results.get(r_type)
                    else set(ids)
                    for r_type, ids in res.extract_references(ref_param).items()
                    if r_type in self.context.resource_types
                }

            # if the _has predicates did not match any documents, return an empty result
            # FIXME: we use the result of the last _has query to build the empty bundle,
            # but we should be more explicit about the query context.
            if not self.reverse_chaining_results:
                return self.response(res, [], as_json)

        # MAIN QUERY
        self.main_query = self.build()

        # TODO handle count with _includes
        if self.result_params.get("_summary") == "count":
            main_result = await self.main_query.count_raw()
        else:
            main_result = await self.main_query.fetchall()
        assert main_result is not None

        # _include
        self.include_queries = self.include(main_result)
        include_results: List[EngineResult] = [
            await q.fetchall() for q in self.include_queries
        ]

        # _revinclude
        self.rev_include_queries = self.rev_include(main_result)
        rev_include_results: List[EngineResult] = [
            await q.fetchall() for q in self.rev_include_queries
        ]

        all_includes = [*include_results, *rev_include_results]
        return self.response(main_result, all_includes, as_json)


def fhir_search(
    context: SearchContext,
    query_string: str = None,
    params: Union[Dict[str, str], Tuple[Tuple[str, str]]] = None,
    response_as_dict: bool = False,
):
    """ """
    if TYPE_CHECKING:
        klass: Union[Type[AsyncSearch], Type[Search]]
    if context.engine.__class__.is_async():
        klass = AsyncSearch
    else:
        klass = Search
    factory = klass(context, query_string=query_string, params=params)
    return factory(as_json=response_as_dict)
