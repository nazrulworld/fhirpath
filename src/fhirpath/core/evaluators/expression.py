# _*_ coding: utf-8 _*_
from typing import Any, List, Optional, TYPE_CHECKING

from .base import EvaluatorBase, LogicalOperator
from ..evaluation import ValuedEvaluation, VerdictEvaluation, Evaluation
from .invocation import MemberInvocationEvaluator
from ..utils import ensure_array, simplify

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

if TYPE_CHECKING:
    from ..element import Element


class IndexerExpressionEvaluator(EvaluatorBase):
    """ """

    __antlr4_node_type__ = "IndexerExpression"

    def __init__(
        self,
        operator: str,
        expression: Optional[str] = None,
    ):
        """ """
        EvaluatorBase.__init__(self, expression)

    def init(self, member_invocation: MemberInvocationEvaluator, index: int):
        """ """
        self.add_node(member_invocation)
        self.add_node(index)

    def evaluate(self, elements: List["Element"]) -> ValuedEvaluation:
        """ """
        elements = ensure_array(elements)
        nodes = self.get_nodes()
        member_invocation = nodes.left
        index = nodes.right
        evaluation = member_invocation.evaluate(elements)
        try:
            return ValuedEvaluation(evaluation.get_value()[index])
        except IndexError:
            return ValuedEvaluation([])


class OrExpressionEvaluator(LogicalOperator):
    __operators__ = {"or": "or_", "xor": "xor"}
    __antlr4_node_type__ = "OrExpression"

    def or_(
        self,
        left_evaluation: VerdictEvaluation,
        right_evaluation: VerdictEvaluation,
    ) -> VerdictEvaluation:
        """ """
        if (
            left_evaluation.get_verdict() is True
            or right_evaluation.get_verdict() is True
        ):
            return VerdictEvaluation([True])
        return VerdictEvaluation([False])

    def xor(
        self,
        left_evaluation: VerdictEvaluation,
        right_evaluation: VerdictEvaluation,
    ) -> VerdictEvaluation:
        """ """
        if not (
            all([left_evaluation.get_verdict(), right_evaluation.get_verdict()])
            or all(
                [not left_evaluation.get_verdict(), not right_evaluation.get_verdict()]
            )
        ) and any([left_evaluation.get_verdict(), right_evaluation.get_verdict()]):
            return VerdictEvaluation([True])
        return VerdictEvaluation([False])


class AndExpressionEvaluator(LogicalOperator):
    __operators__ = {"and": "and_"}
    __antlr4_node_type__ = "AndExpression"

    def and_(
        self,
        left_evaluation: VerdictEvaluation,
        right_evaluation: VerdictEvaluation,
    ) -> VerdictEvaluation:
        """ """
        if all([left_evaluation.get_verdict(), right_evaluation.get_verdict()]):
            return VerdictEvaluation([True])

        return VerdictEvaluation([False])


class EqualityExpressionEvaluator(LogicalOperator):
    """http://hl7.org/fhirpath/N1/#equality
    ~ (Equivalence)
    Equivalence works in exactly the same manner, but with the addition that for complex types,
    equality requires all child properties to be equal, except for "id" elements.
    In addition, for Coding values, equivalence is defined based on the code and
    system elements only. The version, display, and userSelected elements are ignored for
    the purposes of determining Coding equivalence.
    For CodeableConcept values, equivalence is defined as a non-empty intersection of Coding elements,
    using equivalence. In other words, two CodeableConcepts are considered equivalent if any
    Coding in one is equivalent to any Coding in the other.
    """

    __operators__ = {
        "=": "eq",
        "~": "equivalent",
        "!=": "ne",
        "!~": "undefined",
    }
    __antlr4_node_type__ = "EqualityExpression"

    def eq(
        self,
        left_evaluation: Evaluation,
        right_evaluation: Evaluation,
    ) -> VerdictEvaluation:
        """ """
        # @todo: blind compare?
        return VerdictEvaluation(
            [simplify(left_evaluation.get_value(True)) == simplify(right_evaluation.get_value(True))]
        )

    def ne(self, left_evaluation: Evaluation, right_evaluation: Evaluation) -> VerdictEvaluation:
        """6.1.3. != (Not Equals)
        The converse of the equals operator, returning true if equal returns false;
        false if equal returns true; and empty ({ }) if equal returns empty.
        In other words, A != B is short-hand for (A = B).not()."""
        # @todo: blind compare?
        return VerdictEvaluation(
            [simplify(left_evaluation.get_value(True)) != simplify(right_evaluation.get_value(True))]
        )

    def equivalent(self):
        """6.1.2. ~ (Equivalent)
        Returns true if the collections are the same. In particular, comparing empty collections for
        equivalence { } ~ { } will result in true.
        If both operands are collections with a single item, they must be of the same type
        (or implicitly convertible to the same type), and:

        For primitives

        String: the strings must be the same, ignoring case and locale, and normalizing
        whitespace (see String Equivalence for more details).

        Integer: exactly equal

        Decimal: values must be equal, comparison is done on values
        rounded to the precision of the least precise operand. Trailing zeroes after t
        he decimal are ignored in determining precision.

        Date, DateTime and Time: values must be equal, except that if the input values
        have different levels of precision, the comparison returns false, not empty ({ }).

        Boolean: the values must be the same

        For complex types, equivalence requires all child properties to be equivalent, recursively.

        If both operands are collections with multiple items:

        Each item must be equivalent

        Comparison is not order dependent

        Note that this implies that if the collections have a different number of items to compare,
        or if one input is a value and the other is empty ({ }), the result will be false.

        Quantity Equivalence
        When comparing quantities for equivalence, the dimensions of each quantity must be the same,
         but not necessarily the unit. For example, units of 'cm' and 'm' can be compared,
         but units of 'cm2' and 'cm' cannot. The comparison will be made using the most granular
         unit of either input. Attempting to operate on quantities with invalid units will result in false.

        For time-valued quantities, calendar durations and definite quantity durations are
         considered equivalent:

        1 year ~ 1 'a' // true
        1 second ~ 1 's' // true
        Implementations are not required to fully support operations on units,
         but they must at least respect units, recognizing when units differ.

        Implementations that do support units shall do so as specified by [UCUM] as
        well as the calendar durations as defined in the toQuantity function.

        Date/Time Equivalence
        For Date, DateTime and Time equivalence, the comparison is the same as for equality,
         with the exception that if the input values have different levels of precision,
          the result is false, rather than empty ({ }). As with equality, the second and millisecond
          precisions are considered a single precision using a decimal, with decimal equivalence semantics.
        For example:
        @2012 ~ @2012 // returns true
        @2012 ~ @2013 // returns false
        @2012-01 ~ @2012 // returns false as well
        @2012-01-01T10:30 ~ @2012-01-01T10:30 // returns true
        @2012-01-01T10:30 ~ @2012-01-01T10:31 // returns false
        @2012-01-01T10:30:31 ~ @2012-01-01T10:30 // returns false as well
        @2012-01-01T10:30:31.0 ~ @2012-01-01T10:30:31 // returns true
        @2012-01-01T10:30:31.1 ~ @2012-01-01T10:30:31 // returns false
        String Equivalence
        For strings, equivalence returns true if the strings are the same value while
        ignoring case and locale, and normalizing whitespace. Normalizing whitespace means
        that all whitespace characters are treated as equivalent, with whitespace characters as
        defined in the Whitespace lexical category.
        """


class InequalityExpressionEvaluator(LogicalOperator):
    """ """

    __operators__ = {"<=": "le", "<": "lt", ">": "gt", ">=": "ge"}
    __antlr4_node_type__ = "InequalityExpression"

    @staticmethod
    def pre_check(
        left_evaluation: Evaluation, right_evaluation: Evaluation
    ) -> Optional[Evaluation]:
        """ """
        if (len(left_evaluation.get_value()) != len(right_evaluation.get_value())) or not all(
            [left_evaluation.get_verdict(), right_evaluation.get_verdict()]
        ):

            return LogicalOperator.return_false()

    def lt(
        self, left_evaluation: Evaluation, right_evaluation: Evaluation
    ) -> VerdictEvaluation:
        """ """
        evaluation = InequalityExpressionEvaluator.pre_check(
            left_evaluation, right_evaluation
        )
        if evaluation is not None:
            return evaluation

        if len(left_evaluation.get_value()) == 1:
            try:
                return VerdictEvaluation(
                    [simplify(left_evaluation.get_value(True)) < simplify(right_evaluation.get_value(True))]
                )
            except TypeError as exc:
                # @TODO: logging
                return LogicalOperator.return_false()

        result = []
        for idx, value in left_evaluation.get_value():
            result.append(simplify(value) < simplify(right_evaluation.get_value()[idx]))
        return VerdictEvaluation(result)

    def gt(self, left_evaluation: Evaluation, right_evaluation: Evaluation):
        """ """
        evaluation = InequalityExpressionEvaluator.pre_check(
            left_evaluation, right_evaluation
        )
        if evaluation is not None:
            return evaluation

        if len(left_evaluation.get_value()) == 1:
            try:
                return Evaluation(
                    [simplify(left_evaluation.get_value()) > simplify(right_evaluation.get_value())]
                )
            except TypeError as exc:
                # @TODO: logging
                return LogicalOperator.return_false()

        result = []
        for idx, value in left_evaluation.get_value():
            result.append(simplify(value) > simplify(right_evaluation.get_value()[idx]))
        return Evaluation(result)

    def le(self, left_evaluation: Evaluation, right_evaluation: Evaluation):
        """ """
        evaluation = InequalityExpressionEvaluator.pre_check(
            left_evaluation, right_evaluation
        )
        if evaluation is not None:
            return evaluation

        if len(left_evaluation.get_value()) == 1:
            try:
                return Evaluation(
                    [
                        simplify(left_evaluation.get_value())
                        <= simplify(right_evaluation.get_value())
                    ]
                )
            except TypeError as exc:
                # @TODO: logging
                return LogicalOperator.return_false()

        result = []
        for idx, value in left_evaluation.get_value():
            result.append(simplify(value) <= simplify(right_evaluation.get_value()[idx]))
        return Evaluation(result)

    def ge(self, left_evaluation: Evaluation, right_evaluation: Evaluation):
        """ """
        evaluation = InequalityExpressionEvaluator.pre_check(
            left_evaluation, right_evaluation
        )
        if evaluation is not None:
            return evaluation

        if len(left_evaluation.get_value()) == 1:
            try:
                return Evaluation(
                    [
                        simplify(left_evaluation.get_value())
                        >= simplify(right_evaluation.get_value())
                    ]
                )
            except TypeError as exc:
                # @TODO: logging
                return LogicalOperator.return_false()

        result = []
        for idx, value in left_evaluation.get_value():
            result.append(simplify(value) >= simplify(right_evaluation.get_value()[idx]))
        return Evaluation(result)


class MembershipExpressionEvaluator(LogicalOperator):
    """ """

    __operators__ = {"in": "in_", "contains": "contains"}
    __antlr4_node_type__ = "MembershipExpression"

    def in_(self, left_evaluation: Evaluation, right_evaluation: Evaluation):
        """6.4.2. in (membership)
        If the left operand is a collection with a single item, this operator returns true if the item
        is in the right operand using equality semantics. If the left-hand side of the operator is empty,
        the result is empty, if the right-hand side is empty, the result is false.
        If the left operand has multiple items, an exception is thrown.
        The following example returns true if 'Joe' is in the list
        of given names for the Patient:
        'Joe' in Patient.name.given
        """
        value_left, value_right = left_evaluation.get_value(), right_evaluation.get_value()
        if len(value_left) == 0:
            return Evaluation([])
        if len(value_right) == 0:
            return LogicalOperator.return_false()
        if len(value_left) > 1:
            raise ValueError
        return Evaluation(simplify(value_left) in value_right)

    def contains(self, left_evaluation: Evaluation, right_evaluation: Evaluation):
        """6.4.3. contains (containership)
        If the right operand is a collection with a single item, this operator returns true
        if the item is in the left operand using equality semantics. If the right-hand side
        of the operator is empty, the result is empty, if the left-hand side is empty,
        the result is false. This is the converse operation of in.

        The following example returns true if the list of given names for
        the Patient has 'Joe' in it:
        Patient.name.given contains 'Joe'
        """
        value_left, value_right = left_evaluation.get_value(), right_evaluation.get_value()
        if len(value_right) == 0:
            return Evaluation([])
        if len(value_left) == 0:
            return LogicalOperator.return_false()
        if len(value_right) > 1:
            raise ValueError
        return Evaluation(simplify(value_right) in value_left)


class TypeExpressionEvaluator(LogicalOperator):
    """6.3. Types"""

    __operators__ = {"is": "is_", "as": "as_"}
    __antlr4_node_type__ = "TypeExpression"

    def is_(self, left_evaluation: Evaluation, right_evaluation: Evaluation):
        """6.3.1. is type specifier
        If the left operand is a collection with a single item and the second operand
        is a type identifier, this operator returns true if the type of the left
        operand is the type specified in the second operand, or a subclass thereof.
        If the input value is not of the type, this operator returns false.
        If the identifier cannot be resolved to a valid type identifier,
        the evaluator will throw an error. If the input collections contains more than one item,
        the evaluator will throw an error. In all other cases this operator returns the empty collection.

        A type specifier is an identifier that must resolve to the name of a type in a model.
        Type specifiers can have qualifiers,
        e.g. FHIR.Patient, where the qualifier is the name of the model.

        Patient.contained.all($this is Patient implies age > 10)
        :return:
        """
        raise NotImplementedError

    def as_(self, left_evaluation: Evaluation, right_evaluation: Evaluation):
        """6.3.3. as type specifier
        If the left operand is a collection with a single item and the second operand is an
        identifier, this operator returns the value of the left operand if it is of the type
        specified in the second operand, or a subclass thereof. If the identifier cannot be
        resolved to a valid type identifier, the evaluator will throw an error.
        If there is more than one item in the input collection, the evaluator will throw an error.
        Otherwise, this operator returns the empty collection.

        A type specifier is an identifier that must resolve to the name of a type in a model.
        Type specifiers can have qualifiers,
        e.g. FHIR.Patient, where the qualifier is the name of the model.

        Observation.component.where(value as Quantity > 30 'mg')
        :return:
        """
        raise NotImplementedError


class ImpliesExpressionEvaluator(LogicalOperator):
    """6.5.5. implies
    If the left operand evaluates to true, this operator returns the boolean evaluation of
    the right operand. If the left operand evaluates to false, this operator returns true.
    Otherwise, this operator returns true if the right operand evaluates to true,
    and the empty collection ({ }) otherwise.
    The implies operator is useful for testing conditionals. For example,
    if a given name is present, then a family name must be as well:

    Patient.name.given.exists() implies Patient.name.family.exists()
    CareTeam.onBehalfOf.exists() implies (CareTeam.member.resolve() is Practitioner)
    StructureDefinition.contextInvariant.exists() implies StructureDefinition.type = 'Extension'
    Note that implies may use short-circuit evaluation in the case that the first operand evaluates to false.
    """

    __operators__ = {
        "implies": "implies",
    }
    __antlr4_node_type__ = "ImpliesExpression"

    def implies(self, left_evaluation: Evaluation, right_evaluation: Evaluation):
        """ """
        if len(left_evaluation.get_value()) == 0:
            if (
                len(right_evaluation.get_value()) == 0
                or right_evaluation.get_verdict() is False
            ):
                return Evaluation([])
            return LogicalOperator.return_true()
        if left_evaluation.get_verdict() is True:
            return Evaluation(right_evaluation.get_verdict())
        else:
            return LogicalOperator.return_true()


__all__ = [
    "MembershipExpressionEvaluator",
    "InequalityExpressionEvaluator",
    "EqualityExpressionEvaluator",
    "AndExpressionEvaluator",
    "OrExpressionEvaluator",
    "IndexerExpressionEvaluator",
    "ImpliesExpressionEvaluator",
    "TypeExpressionEvaluator"
]
