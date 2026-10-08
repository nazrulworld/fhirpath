# _*_ coding: utf-8 _*_
"""Most of codes are copied from https://github.com/nazrulworld/fhir-parser
and modified in terms of styling, unnecessary codes cleanup
(those are not relevant for this package)
"""
import io
import json
import logging
import pathlib
import re
from collections import defaultdict
from copy import copy
from typing import TYPE_CHECKING, List, Set

from fhirpath.enums import FHIR_VERSION
from ..interfaces import IStorage
from .expression import UnsupportedExpression, element_paths, split_by_base
from ..storage import MemoryStorage
from fhirpath.utils import reraise

logger = logging.getLogger("fhirpath.fhrspec")

# allow to skip some profiles by matching against their url (used while WiP)
skip_because_unsupported = [r"SimpleQuantity"]
HTTP_URL = re.compile(r"^https?://", re.IGNORECASE)


types_with_prefix: Set[str] = {"number", "date", "quantity"}
search_param_prefixes: Set[str] = {
    "eq",
    "ne",
    "gt",
    "lt",
    "ge",
    "le",
    "sa",
    "eb",
    "ap",
}


class FHIRSearchSpec(object):
    """https://www.hl7.org/fhir/searchparameter-registry.html"""

    def __init__(
        self, source: pathlib.Path, fhir_release: FHIR_VERSION, storage: MemoryStorage
    ):
        """ """
        self._finalized = False
        self.source = source
        self.storage = IStorage(storage)
        self.fhir_release = FHIR_VERSION.normalize(fhir_release)
        self.parameters_def: List[SearchParameterDefinition] = list()
        self.prepare()

    def prepare(self):
        """ """
        with io.open(str(self.source / self.jsonfilename), "r", encoding="utf-8") as fp:
            string_val = fp.read()
            spec_dict = json.loads(string_val)

        for entry in spec_dict["entry"]:

            self.parameters_def.append(
                SearchParameterDefinition.from_dict(self, entry["resource"])
            )

        # composite components refer to other definitions; remember their type,
        # which decides how the component value is parsed. STU3 references the
        # definition with a Reference ({"reference": url}), later releases with
        # a canonical
        types = {
            entry["resource"].get("url"): entry["resource"]["type"]
            for entry in spec_dict["entry"]
        }
        for param_def in self.parameters_def:
            for component in param_def.component or []:
                definition = component.get("definition")
                if isinstance(definition, dict):
                    definition = definition.get("reference")
                component["_type"] = types.get(definition)

    def write(self):
        """ """
        storage = self.storage.get(self.fhir_release.name)

        for param_def in self.parameters_def:
            for resource_type in param_def.expression_map:
                if not storage.exists(resource_type):
                    storage.insert(
                        resource_type, ResourceSearchParameterDefinition(resource_type)
                    )
                obj = storage.get(resource_type)
                # add search param code to obj
                setattr(
                    obj,
                    param_def.code,
                    SearchParameter.from_definition(resource_type, param_def),
                )

        self.apply_base_resource_params()

    def apply_base_resource_params(self):
        """ """
        storage = self.storage.get(self.fhir_release.name)
        base_resource_params = storage.get("Resource")
        base_domain_resource_params = storage.get("DomainResource")

        for resource_type in storage:
            if resource_type in ("Resource", "DomainResource"):
                continue
            storage.get(resource_type) + base_resource_params
            storage.get(resource_type) + base_domain_resource_params

    @property
    def jsonfilename(self):
        """ """
        return "search-parameters.json"


class SearchParameterDefinition(object):
    """ """

    if TYPE_CHECKING:
        spec = None
        name: None
        code: None
        expression_map: None
        type: None
        modifier: None
        comparator: None
        target: None
        xpath: None
        multiple_or: None
        multiple_and: None
        component: None
        processing_mode: None

    __slots__ = (
        "spec",
        "name",
        "code",
        "expression_map",
        "type",
        "modifier",
        "comparator",
        "target",
        "xpath",
        "multiple_or",
        "multiple_and",
        "component",
        "processing_mode",
    )

    @classmethod
    def from_dict(cls, spec, dict_value):
        """ """
        self = cls()
        self.spec = spec
        self.name = dict_value["name"]
        self.code = dict_value["code"]
        self.type = dict_value["type"]

        # Add conditional None
        self.xpath = dict_value.get("xpath")
        self.modifier = dict_value.get("modifier", None)
        self.comparator = dict_value.get("comparator", None)
        self.target = dict_value.get("target", None)
        self.multiple_or = dict_value.get("multipleOr", None)
        self.multiple_and = dict_value.get("multipleAnd", None)
        self.component = dict_value.get("component", None)
        # R5 processingMode (R4 xpathUsage): normal | phonetic | other
        self.processing_mode = dict_value.get(
            "processingMode", dict_value.get("xpathUsage", None)
        )

        # Make expression map combined with base and expression: each base gets
        # its own branches of a shared expression (bases without any are None)
        self.expression_map = {base: None for base in dict_value["base"]}
        expression = dict_value.get("expression", None)
        if expression:
            self.expression_map.update(
                split_by_base(expression.replace("\u200b", ""), dict_value["base"])
            )

        return self


class SearchParameter(object):
    """ """

    if TYPE_CHECKING:
        name: None
        code: None
        expression: None
        type: None
        modifier: None
        comparator: None
        target: None
        xpath: None
        multiple_or: None
        multiple_and: None
        component: None
        processing_mode: None

    __slots__ = (
        "name",
        "code",
        "expression",
        "type",
        "modifier",
        "comparator",
        "target",
        "xpath",
        "multiple_or",
        "multiple_and",
        "component",
        "processing_mode",
    )

    @classmethod
    def from_definition(cls, resource_type, definition):
        """ """
        self = cls()
        self.name = definition.name
        self.code = definition.code
        self.type = definition.type
        self.xpath = definition.xpath
        self.modifier = definition.modifier
        self.comparator = definition.comparator
        self.target = definition.target
        self.multiple_or = definition.multiple_or
        self.multiple_and = definition.multiple_and
        self.component = definition.component
        self.processing_mode = definition.processing_mode
        self.expression = self.get_expression(resource_type, definition)

        return self

    def get_expression(self, resource_type, definition):
        """The FHIRPath expression of this parameter for ``resource_type``
        (every branch, normalized by the FHIRPath parser)."""
        return definition.expression_map[resource_type]

    def element_paths(self) -> List[str]:
        """Dotted element paths the expression selects (one per union branch);
        raises :class:`UnsupportedExpression` when there is none."""
        if not self.expression:
            raise UnsupportedExpression(
                f"search parameter {self.code} has no expression"
            )
        return element_paths(self.expression)

    def clone(self):
        """ """
        return self.__copy__()

    def support_prefix(self):
        return self.type in types_with_prefix

    def __copy__(self):
        """ """
        newone = type(self).__new__(type(self))
        newone.name = copy(self.name)
        newone.code = copy(self.code)
        newone.type = copy(self.type)
        newone.xpath = copy(self.xpath)
        newone.modifier = copy(self.modifier)
        newone.comparator = copy(self.comparator)
        newone.target = copy(self.target)
        newone.multiple_or = copy(self.multiple_or)
        newone.multiple_and = copy(self.multiple_and)
        newone.component = copy(self.component)
        newone.processing_mode = copy(self.processing_mode)
        newone.expression = copy(self.expression)

        return newone


class ResourceSearchParameterDefinition(object):
    """ """

    __slots__ = ("__storage__", "_finalized", "resource_type")

    def __init__(self, resource_type):
        """ """
        object.__setattr__(self, "__storage__", defaultdict())
        object.__setattr__(self, "_finalized", False)
        object.__setattr__(self, "resource_type", resource_type)

    def __getattr__(self, item):
        """
        :param item:
        :return:
        """
        try:
            return self.__storage__[item]
        except KeyError:
            msg = "Object from {0!s} has no attribute `{1}`".format(
                self.__class__.__name__, item
            )
            reraise(AttributeError, msg)

    def __setattr__(self, name, value):
        """ """
        if self._finalized:
            raise TypeError("Modification of attribute value is not allowed!")

        self.__storage__[name] = value

    def __delattr__(self, item):
        """ """
        if self._finalized:
            raise TypeError("Modification of attribute value is not allowed!")

        try:
            del self.__storage__[item]
        except KeyError:
            msg = "Object from {0!s} has no attribute `{1}`".format(
                self.__class__.__name__, item
            )
            reraise(AttributeError, msg)

    def __add__(self, other):
        """ """
        for key, val in other.__storage__.items():
            copied = val.clone()
            if copied.expression and other.resource_type in copied.expression:
                copied.expression = copied.expression.replace(
                    other.resource_type, self.resource_type
                )

            if copied.xpath and other.resource_type in copied.xpath:
                copied.xpath = copied.xpath.replace(
                    other.resource_type, self.resource_type
                )

            self.__storage__[key] = copied

    def __iter__(self):
        """ """
        for key in self.__storage__:
            yield key

    def __contains__(self, item):
        """ """
        return item in self.__storage__
