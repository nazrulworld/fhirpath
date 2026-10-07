# _*_ coding: utf-8 _*_
"""Errors signalled to the calling environment by the FHIRPath engine."""

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class EvaluationError(Exception):
    """A FHIRPath error ("signal an error to the calling environment").

    ``expression`` is the (sub-)expression being evaluated when the error occurred.
    """

    def __init__(self, msg: str, expression: str = ""):
        Exception.__init__(self, msg)
        self.msg = msg
        self.expression = expression

    def __str__(self):
        if self.expression:
            return "%s (in %r)" % (self.msg, self.expression)
        return self.msg


__all__ = ["EvaluationError"]
