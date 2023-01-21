# _*_ coding: utf-8 _*_
from collections import deque
from typing import Any, TYPE_CHECKING, Optional, Deque, List
from typing import cast

from ..evaluation import Evaluation, VerdictEvaluation, EvaluationError, ValuedEvaluation
from ..utils import (
    LeftRightTuple,
    EMPTY,
)

if TYPE_CHECKING:
    from ..element import Element

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class EvaluatorBase:
    """2.9.1.4 FHIR Specific Variables
    FHIR defines two specific variables that are always in scope when FHIRPath is
    used in any of the contexts above:

    %resource // the resource that contains the original node that is in %context
    %rootResource // the container resource for the resource identified by %resource
    The resource is very often the context, such that %resource = %context.
    When a DomainResource contains another resource, and that contained resource
    is the focus (%resource) then %rootResource refers to the container resource.
    Note that in most cases, the resource is not contained by another resource,
    and then %rootResource is the same as %resource."""

    __antlr4_node_type__: str = ""
    __slots__ = ("__expression_literal__", "__storage__", "__predecessor__")

    def __init__(self, expression: Optional[str] = None):
        """ """
        self.__expression_literal__ = expression
        self.__predecessor__: Optional["EvaluatorBase"] = None
        self.__storage__: Deque[Any] = deque(maxlen=2)

    def evaluate(self, elements: List["Element"]) -> Evaluation:
        """ """
        raise NotImplementedError

    def get_type(self):
        """ """
        return self.__antlr4_node_type__

    def get_expression(self):
        """ """
        return self.__expression_literal__

    def add_node(self, node: Any):
        """ """
        if len(self.__storage__) > 2:
            raise ValueError("left & right values are already assigned")
        self.__storage__.append(node)

    def get_nodes(self) -> LeftRightTuple:
        """ """
        if len(self.__storage__) == 0:
            return LeftRightTuple(EMPTY, EMPTY)
        elif len(self.__storage__) == 1:
            return LeftRightTuple(self.__storage__[0], EMPTY)
        else:
            return LeftRightTuple(self.__storage__[0], self.__storage__[1])

    def set_predecessor(self, evaluator: "EvaluatorBase"):
        """ """
        self.__predecessor__ = evaluator

    def get_predecessor(self):
        """ """
        return self.__predecessor__

    @staticmethod
    def ensure_evaluation(value: Any):
        """ """
        if isinstance(value, Evaluation):
            return value
        return ValuedEvaluation(value)


class LogicalOperator(EvaluatorBase):
    """ """

    __operators__ = {}
    __slots__ = ("operator",) + Evaluation.__slots__

    def __init__(
        self,
        operator: str,
        expression: Optional[str] = None,
    ):
        """ """
        EvaluatorBase.__init__(self, expression)

        if operator not in self.__operators__.keys():
            raise TypeError(f"Invalid operator for '{self.__antlr4_node_type__}'.")
        self.operator = operator

    def init(self, node_left: Any, node_right: Any):
        """ """
        self.add_node(node_left)
        self.add_node(node_right)

    def validate(
        self, value_left: Any, value_right: Any = EMPTY
    ) -> Optional[Evaluation]:
        """ """
        if isinstance(value_left, EvaluationError):
            raise ValueError
        if isinstance(value_right, EvaluationError):
            raise ValueError
        return

    def evaluate(self, elements: List["Element"] = EMPTY) -> VerdictEvaluation:
        """ """
        nodes = self.get_nodes()
        evaluation_left = LogicalOperator.extract_value(nodes.left, elements)
        evaluation_right = LogicalOperator.extract_value(nodes.right, elements)
        self.validate(evaluation_left, evaluation_right)
        return getattr(self, self.__operators__[self.operator])(
            evaluation_left, evaluation_right
        )

    @staticmethod
    def return_false() -> VerdictEvaluation:
        """ """
        return VerdictEvaluation([False])

    @staticmethod
    def return_true() -> Evaluation:
        """ """
        return VerdictEvaluation([True])

    @staticmethod
    def extract_value(node: Any, resource: Any = EMPTY) -> Any:
        """ """
        if node is EMPTY and resource is not EMPTY:
            return EvaluatorBase.ensure_evaluation(resource)
        if resource is EMPTY and isinstance(node, EvaluatorBase):
            raise ValueError
        if isinstance(node, EvaluatorBase):
            return node.evaluate(resource)
        return EvaluatorBase.ensure_evaluation(node)


class ParenthesizedTermEvaluator(EvaluatorBase):
    """ """

    __antlr4_node_type__ = "ParenthesizedTerm"

    def evaluate(self, elements: List["Element"]) -> Evaluation:
        """ """
        if len(self.__storage__) == 0:
            raise ValueError("No successor evaluator is assigned.")
            # raise EvaluationError()
        successor = self.__storage__[0]
        if TYPE_CHECKING:
            successor = cast(EvaluatorBase, successor)
        return successor.evaluate(elements)

    def add_node(self, node: EvaluatorBase):
        """ """
        if len(self.__storage__) > 0:
            raise ValueError("Successor evaluator is already assigned.")
        self.__storage__.append(node)


__all__ = [
    "EvaluatorBase",
    "EvaluationError",
    "ParenthesizedTermEvaluator",
]
