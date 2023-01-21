# _*_ coding: utf-8 _*_
import logging
from typing import Any, List, Optional, TYPE_CHECKING, cast

from ..evaluation import Evaluation, ValuedEvaluation
from .base import EvaluatorBase
from ..utils import ensure_array, has_value, PRIMITIVES, EMPTY

if TYPE_CHECKING:
    from ..element import Element

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

LOG = logging.getLogger("evaluator.invocation")


class InvocationExpressionEvaluator(EvaluatorBase):
    __antlr4_node_type__ = "InvocationExpression"

    def init(self, node_left: EvaluatorBase, node_right: EvaluatorBase):
        """ """
        self.add_node(node_left)
        self.add_node(node_right)

    def evaluate(self, elements: List["Element"]) -> Evaluation:
        """ """
        nodes = self.get_nodes()
        value_evaluation = nodes.left.evaluate(elements)
        if nodes.right is EMPTY:
            return value_evaluation
        return nodes.right.evaluate(value_evaluation.get_value())


class FunctionInvocationEvaluator(EvaluatorBase):
    """TODO: inspect function"""

    __antlr4_node_type__ = "FunctionInvocation"
    __slots__ = (
        "func_name",
        "param_list",
    ) + EvaluatorBase.__slots__

    def __init__(
        self,
        expression: str = None,
    ):
        """param_list: (param name, param value, EqualityExpression)"""
        EvaluatorBase.__init__(self, expression)
        self.func_name: str = ""
        self.param_list: Optional[List[EvaluatorBase]] = None

    def init(self, func_name: str, param_list: Optional[List[EvaluatorBase]] = None):
        try:
            if func_name in ("not", "is", "as"):
                func_name += "_"
            getattr(self, func_name)
            self.func_name = func_name
        except AttributeError:
            raise ValueError
        self.param_list = param_list

    def evaluate(self, elements: List["Element"]) -> Evaluation:
        """ """
        return getattr(self, self.func_name)(elements)

    def where(self, elements: List["Element"]) -> ValuedEvaluation:
        """5.2. Filtering and projection
        5.2.1. where(criteria : expression) : collection
        Returns a collection containing only those elements in the input collection for
        which the stated criteria expression evaluates to true. Elements for which the expression
        evaluates to false or empty ({ }) are not included in the result.

        If the input collection is empty ({ }), the result is empty.

        If the result of evaluating the condition is other than a single boolean value,
        the evaluation will end and signal an error to the calling environment, consistent with
        singleton evaluation of collections behavior.

        The following example returns the list of telecom elements that have a use element with the
        value of 'official':
        Patient.telecom.where(use = 'official')
        """
        result = []
        elements = ensure_array(elements)
        expanded_elements = elements[0].__class__.flatten_elements(elements)
        for el in expanded_elements:
            if all(
                [
                    evaluator.evaluate(el).get_verdict()
                    for evaluator in self.param_list
                ]
            ):
                result.append(el)
        return ValuedEvaluation(result)

    def count(self, collection: List[Any]):
        """5.1.10. count() : Integer
        Returns the integer count of the number of items in the input collection.
        Returns 0 when the input collection is empty.
        :return:
        """
        return ValuedEvaluation(len(collection))

    def exists(self, collection: List[Any]) -> Evaluation:
        """5.1.2. exists([criteria : expression]) : Boolean
        Returns true if the collection has any elements, and false otherwise. This is the opposite of empty(),
        and as such is a shorthand for empty().not(). If the input collection is empty ({ }), the result is false.

        The function can also take an optional criteria to be applied to the collection prior to the
        determination of the exists. In this case, the function is shorthand for where(criteria).exists().

        Note that a common term for this function is any.

        The following examples illustrate some potential uses of the exists() function:

        Patient.name.exists()
        Patient.identifier.exists(use = 'official')
        Patient.telecom.exists(system = 'phone' and use = 'mobile')
        Patient.generalPractitioner.exists($this is Practitioner)
        The first example returns true if the Patient has any name elements.

        The second example returns true if the Patient has any identifier elements that have a use element equal to 'official'.

        The third example returns true if the Patient has any telecom elements that have a system element equal to 'phone' and a use element equal to 'mobile'.

        And finally, the fourth example returns true if the Patient has any generalPractitioner elements of type Practitioner.
        """
        if self.param_list is None:
            return Evaluation([len(collection) > 0])
        eva = self.where(collection)
        return Evaluation(eva.get_verdict())

    def trace(self):
        """5.9.1. trace(name : String [, projection: Expression]) : collection
        Adds a String representation of the input collection to the diagnostic log, using the name argument as the name in the log. This log should be made available to the user in some appropriate fashion. Does not change the input, so returns the input collection as output.

        If the projection argument is used, the trace would log the result of evaluating the project expression on the input, but still return the input to the trace function unchanged.

        contained.where(criteria).trace('unmatched', id).empty()
        The above example traces only the id elements of the result of the where.
        """

    def empty(self, collection: List[Any]) -> Evaluation:
        """5.1.1. empty() : Boolean
        Returns true if the input collection is empty ({ }) and false otherwise.
        """
        return Evaluation([len(collection) == 0])

    def not_(self, collection: List[Any]):
        """6.5.3. not() : Boolean
        Returns true if the input collection evaluates to false, and false if it evaluates to true. Otherwise, the result is empty ({ }):
        :return:
        """
        if len(collection) > 0:
            return Evaluation([not collection[0]])
        return Evaluation([True])

    def hasValue(self, collection: List[Any]) -> Evaluation:
        """Returns true if the input collection contains a single value which is a FHIR primitive,
        and it has a primitive value (e.g. as opposed to not having a value and just having extensions).
        Otherwise, the return value is empty.

        Note to implementers: The FHIR conceptual model talks about "primitives" as subclasses of the
        type Element that also have id and extensions. What this actually means is that a FHIR primitive
        is not a primitive in an implementation language. The introduction (section 2 above) describes
        the navigation tree as if the FHIR model applies - primitives are both primitives and elements
        with children.
        In FHIRPath, this means that FHIR primitives have a value child, but,
        as described above, they are automatically cast to FHIRPath primitives when
        comparisons are made, and that the primitive value will be included in the set
        returned by children() or descendants().
        """
        ignores = ["id", "resourceType"]
        results = []
        for item in collection:
            for key, val in item.items():
                if key in ignores:
                    continue
                if isinstance(val, PRIMITIVES):
                    results.append(True)
                    break
        return Evaluation(results)

    def children(self, collection: List[Any]) -> Evaluation:
        """Returns a collection with all immediate child nodes of all items
        in the input collection. Note that the ordering of the children is
        undefined and using functions like first() on the result may return
        different results on different platforms."""
        result = []
        try:
            for item in collection:
                result.append(list(item.values()))
        except AttributeError:
            pass
        return Evaluation(result)

    def descendants(self):
        """5.8.2. descendants() : collection
        Returns a collection with all descendant nodes of all items in the input collection.
        The result does not include the nodes in the input collection themselves.
        This function is a shorthand for repeat(children()).
        Note that the ordering of the children is undefined and using functions like first()
        on the result may return different results on different platforms.

        Note: Many of these functions will result in a set of nodes of different underlying types.
        It may be necessary to use ofType() as described in the previous section to maintain
        type safety. See Type safety and strict evaluation for more information about type safe use
        of FHIRPath expressions.
        """

    def as_(self):
        """6.3.4. as(type : type specifier)
        The as() function is supported for backwards compatibility with previous
        implementations of FHIRPath. Just as with the as keyword, the type argument is an identifier
        that must resolve to the name of a type in a model. For implementations with compile-time typing, this requires special-case handling when processing the argument to treat is a type specifier rather than an identifier expression:

        Observation.component.where(value.as(Quantity) > 30 'mg')
        Note: The as() function is defined for backwards compatibility only and may be
        deprecated in a future release."""

    def is_(self):
        """ """

    def contains(self, left_evaluation: Evaluation, right_evaluation: Evaluation):
        """Returns true when the given substring is a substring of the input string.
        If substring is the empty string (''), the result is true.
        If the input collection is empty, the result is empty.
        If the input collection contains multiple items, the evaluation of the expression
        will end and signal an error to the calling environment.

        'abc'.contains('b') // true
        'abc'.contains('bc') // true
        'abc'.contains('d') // false
        Note: The .contains() function described here is a string function that looks
        for a substring in a string. This is different than the contains operator,
        which is a list operator that looks for an element in a list.
        """


class MemberInvocationEvaluator(EvaluatorBase):
    __antlr4_node_type__ = "MemberInvocation"
    """https://hl7.github.io/fhirpath.js/"""

    def init(self, identifier: str):
        """ """
        self.add_node(identifier)

    def add_node(self, node: str):
        """ """
        if len(self.__storage__) > 0:
            raise ValueError("identifier is already assigned.")
        self.__storage__.append(node)

    def evaluate(self, elements: List["Element"]) -> Evaluation:
        """ """
        elements = ensure_array(elements)
        result = []
        if TYPE_CHECKING:
            from ..element import Element
            result = cast(List[Element], result)
        nodes = self.get_nodes()
        for element in elements:
            collection = ensure_array(element.element_value())
            for idx, obj in enumerate(collection):
                try:
                    val = getattr(obj, nodes.left)
                    if has_value(val):
                        if element.is_collection():
                            result.append(element.element_children()[idx])
                        else:
                            result.append(element.element_children()[element.element_children_map()[nodes.left]])
                except (AttributeError, TypeError) as exc:
                    raise
                    LOG.debug(str(exc), exc_info=exc)

        return ValuedEvaluation(elements[0].__class__.flatten_elements(result))


__all__ = [
    "MemberInvocationEvaluator",
    "FunctionInvocationEvaluator",
    "InvocationExpressionEvaluator",
]
