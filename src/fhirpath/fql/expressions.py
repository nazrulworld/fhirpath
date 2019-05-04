# _*_ coding: utf-8 _*_

__author__ = "Md Nazrul Islam <email2nazrul>"


class Term(object):
    """ """

    def __init__(self, path, value):
        """ """
        self.path = path
        self.value = value
        self.type = None

    def bind(self, context):
        """ """
        # xxx: find type using Context
        # https://github.com/nazrulworld/fhir-parser\
        # /blob/d8c8871147031882011d5e497f3e99fc19863f27/fhirspec.py#L98
        # from there it is possible to calculate ValueType

    def validate(self):
        """ """


def and_(path, value):
    """ """


def or_(path, value):
    """ """


def in_(path, values):
    """ """
