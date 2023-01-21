import abc
from typing import Any, TYPE_CHECKING, List, Union

from .utils import (
    finalize_value,
    ensure_array,
    ReadonlyClass,
)

if TYPE_CHECKING:
    from .element import Element

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class EvaluationError(Exception, ReadonlyClass):
    """@todo: contact errors"""

    __slots__ = ("msg", "expression")

    def __init__(self, msg: str, expression: str):
        """ """
        object.__setattr__(self, "msg", msg)
        object.__setattr__(self, "expression", expression)
        Exception.__init__(self, msg)


class Evaluation(abc.ABC, ReadonlyClass):
    """ """

    if TYPE_CHECKING:
        __value__: List[Any]
    __slots__ = ("__value__",)

    def __init__(self, value: Any):
        """Terms for variable error."""
        value = finalize_value(ensure_array(value))
        self.validate(value)
        object.__setattr__(self, "__value__", value)

    def validate(self, value: List[Any]):
        """ """
        pass

    def get_value(self, extract_element_value=False) -> List[Any]:
        """ """
        if extract_element_value:
            return list(
                map(
                    lambda x: x.__class__.__name__ == "Element"
                    and x.element_value()
                    or x,
                    self.__value__,
                )
            )
        return self.__value__

    def get_verdict(self) -> bool:
        """ """
        raise NotImplementedError

    def __bool__(self) -> bool:
        """ """
        return self.get_verdict()


class ValuedEvaluation(Evaluation):
    """ """

    if TYPE_CHECKING:
        __value__: List[Union[None, "Element"]]

    def get_verdict(self) -> bool:
        """ """
        return len(self.__value__) > 0


class VerdictEvaluation(Evaluation):
    """ """

    if TYPE_CHECKING:
        __value__: List[bool]

    def get_verdict(self) -> bool:
        """ """
        return self.__value__[0]

    def validate(self, value: List[Any]):
        """ """
        if len(value) == 1 and isinstance(value[0], bool):
            return
        raise ValueError("Only boolean value is accepted")
