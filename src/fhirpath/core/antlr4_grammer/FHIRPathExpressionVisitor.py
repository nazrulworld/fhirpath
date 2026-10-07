# Generated from FHIRPathExpression.g4 by ANTLR 4.9.3
from antlr4 import *

if __name__ is not None and "." in __name__:
    from .FHIRPathExpressionParser import FHIRPathExpressionParser
else:
    from FHIRPathExpressionParser import FHIRPathExpressionParser

# This class defines a complete generic visitor for a parse tree produced by FHIRPathExpressionParser.


class FHIRPathExpressionVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by FHIRPathExpressionParser#entireExpression.
    def visitEntireExpression(
        self, ctx: FHIRPathExpressionParser.EntireExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#indexerExpression.
    def visitIndexerExpression(
        self, ctx: FHIRPathExpressionParser.IndexerExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#polarityExpression.
    def visitPolarityExpression(
        self, ctx: FHIRPathExpressionParser.PolarityExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#additiveExpression.
    def visitAdditiveExpression(
        self, ctx: FHIRPathExpressionParser.AdditiveExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#multiplicativeExpression.
    def visitMultiplicativeExpression(
        self, ctx: FHIRPathExpressionParser.MultiplicativeExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#unionExpression.
    def visitUnionExpression(
        self, ctx: FHIRPathExpressionParser.UnionExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#orExpression.
    def visitOrExpression(self, ctx: FHIRPathExpressionParser.OrExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#andExpression.
    def visitAndExpression(self, ctx: FHIRPathExpressionParser.AndExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#membershipExpression.
    def visitMembershipExpression(
        self, ctx: FHIRPathExpressionParser.MembershipExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#inequalityExpression.
    def visitInequalityExpression(
        self, ctx: FHIRPathExpressionParser.InequalityExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#invocationExpression.
    def visitInvocationExpression(
        self, ctx: FHIRPathExpressionParser.InvocationExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#equalityExpression.
    def visitEqualityExpression(
        self, ctx: FHIRPathExpressionParser.EqualityExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#impliesExpression.
    def visitImpliesExpression(
        self, ctx: FHIRPathExpressionParser.ImpliesExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#termExpression.
    def visitTermExpression(self, ctx: FHIRPathExpressionParser.TermExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#typeExpression.
    def visitTypeExpression(self, ctx: FHIRPathExpressionParser.TypeExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#invocationTerm.
    def visitInvocationTerm(self, ctx: FHIRPathExpressionParser.InvocationTermContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#literalTerm.
    def visitLiteralTerm(self, ctx: FHIRPathExpressionParser.LiteralTermContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#externalConstantTerm.
    def visitExternalConstantTerm(
        self, ctx: FHIRPathExpressionParser.ExternalConstantTermContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#parenthesizedTerm.
    def visitParenthesizedTerm(
        self, ctx: FHIRPathExpressionParser.ParenthesizedTermContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#instanceSelectorTerm.
    def visitInstanceSelectorTerm(
        self, ctx: FHIRPathExpressionParser.InstanceSelectorTermContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#nullLiteral.
    def visitNullLiteral(self, ctx: FHIRPathExpressionParser.NullLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#booleanLiteral.
    def visitBooleanLiteral(self, ctx: FHIRPathExpressionParser.BooleanLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#stringLiteral.
    def visitStringLiteral(self, ctx: FHIRPathExpressionParser.StringLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#numberLiteral.
    def visitNumberLiteral(self, ctx: FHIRPathExpressionParser.NumberLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#longNumberLiteral.
    def visitLongNumberLiteral(
        self, ctx: FHIRPathExpressionParser.LongNumberLiteralContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#dateLiteral.
    def visitDateLiteral(self, ctx: FHIRPathExpressionParser.DateLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#dateTimeLiteral.
    def visitDateTimeLiteral(
        self, ctx: FHIRPathExpressionParser.DateTimeLiteralContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#timeLiteral.
    def visitTimeLiteral(self, ctx: FHIRPathExpressionParser.TimeLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#quantityLiteral.
    def visitQuantityLiteral(
        self, ctx: FHIRPathExpressionParser.QuantityLiteralContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#externalConstant.
    def visitExternalConstant(
        self, ctx: FHIRPathExpressionParser.ExternalConstantContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#memberInvocation.
    def visitMemberInvocation(
        self, ctx: FHIRPathExpressionParser.MemberInvocationContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#functionInvocation.
    def visitFunctionInvocation(
        self, ctx: FHIRPathExpressionParser.FunctionInvocationContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#thisInvocation.
    def visitThisInvocation(self, ctx: FHIRPathExpressionParser.ThisInvocationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#indexInvocation.
    def visitIndexInvocation(
        self, ctx: FHIRPathExpressionParser.IndexInvocationContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#totalInvocation.
    def visitTotalInvocation(
        self, ctx: FHIRPathExpressionParser.TotalInvocationContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#function.
    def visitFunction(self, ctx: FHIRPathExpressionParser.FunctionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#sortDirectionArgument.
    def visitSortDirectionArgument(
        self, ctx: FHIRPathExpressionParser.SortDirectionArgumentContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#paramList.
    def visitParamList(self, ctx: FHIRPathExpressionParser.ParamListContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#instanceSelector.
    def visitInstanceSelector(
        self, ctx: FHIRPathExpressionParser.InstanceSelectorContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#instanceElementSelector.
    def visitInstanceElementSelector(
        self, ctx: FHIRPathExpressionParser.InstanceElementSelectorContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#quantity.
    def visitQuantity(self, ctx: FHIRPathExpressionParser.QuantityContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#unit.
    def visitUnit(self, ctx: FHIRPathExpressionParser.UnitContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#dateTimePrecision.
    def visitDateTimePrecision(
        self, ctx: FHIRPathExpressionParser.DateTimePrecisionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#pluralDateTimePrecision.
    def visitPluralDateTimePrecision(
        self, ctx: FHIRPathExpressionParser.PluralDateTimePrecisionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#typeSpecifier.
    def visitTypeSpecifier(self, ctx: FHIRPathExpressionParser.TypeSpecifierContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#qualifiedIdentifier.
    def visitQualifiedIdentifier(
        self, ctx: FHIRPathExpressionParser.QualifiedIdentifierContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by FHIRPathExpressionParser#identifier.
    def visitIdentifier(self, ctx: FHIRPathExpressionParser.IdentifierContext):
        return self.visitChildren(ctx)


del FHIRPathExpressionParser
