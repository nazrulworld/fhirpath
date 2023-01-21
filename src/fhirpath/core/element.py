from abc import ABC
from typing import List, Any, Union, TYPE_CHECKING, Dict, cast

from fhir.resources.core.fhirabstractmodel import FHIRAbstractModel

from .node import compile_expression
from .utils import has_value

if TYPE_CHECKING:
    from .evaluation import ValuedEvaluation, VerdictEvaluation

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


def setup_children_element(self: "Element"):
    """ """
    if isinstance(self.__value__, list):
        for val in self.__value__:
            el = Element(val, self)
            self.__children__.append(el)
    elif isinstance(self.__value__, FHIRAbstractModel):
        for name in self.__value__.elements_sequence():
            """ """
            el = Element(getattr(self.__value__, name), self)
            index = len(self.__children__)
            self.__children__.append(el)
            self.__children_map__[name] = index

    elif isinstance(self.__value__, dict):
        raise NotImplementedError


class Element(ABC):
    """ """

    if TYPE_CHECKING:
        __root__: bool
        __parent__: "Element"
        __children__: List["Element"]
        __children_map__: Dict[str, int]
        __value__: Any

    __slots__ = (
        "__root__",
        "__parent__",
        "__children__",
        "__children_map__",
        "__value__",
    )

    def __init__(self, value, parent=None):
        """ """
        ABC.__setattr__(self, "__value__", value)
        ABC.__setattr__(self, "__parent__", parent)
        if parent is None:
            ABC.__setattr__(self, "__root__", True)
        ABC.__setattr__(self, "__children__", list())
        ABC.__setattr__(self, "__children_map__", dict())
        # setup
        setup_children_element(self)

    def query(self, expression: str) -> List[Union[None, "Element"]]:
        """ """
        if not has_value(self.__value__):
            return []
        evaluation = self.__query__(expression)
        if TYPE_CHECKING:
            evaluation = cast(ValuedEvaluation, evaluation)
        return evaluation.get_value()

    def test(self, expression: str) -> bool:
        """ """
        evaluation = self.__query__(expression)
        return evaluation.get_verdict()

    def __query__(
        self, expression: str
    ) -> Union["ValuedEvaluation", "VerdictEvaluation"]:
        """ """
        expression_node = compile_expression(expression)
        evaluator = expression_node.construct_evaluator()
        evaluation = evaluator.evaluate(self)
        return evaluation

    def __setattr__(self, key, value):
        """ """
        raise TypeError("Readonly object!")

    def is_collection(self):
        """ """
        return isinstance(self.__value__, list)

    @staticmethod
    def flatten_elements(elements: List["Element"]):
        """ """
        holder: List["Element"] = []
        for el in elements:
            if el.is_collection():
                holder.extend(Element.flatten_elements(el.element_children()))
            else:
                holder.append(el)
        return holder

    def element_children(self):
        """ """
        return self.__children__

    def element_parent(self):
        """ """
        return self.__parent__

    def element_value(self):
        """ """
        return self.__value__

    def element_children_map(self):
        """ """
        return self.__children_map__
