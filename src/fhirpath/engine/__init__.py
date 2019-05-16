# _*_ coding: utf-8 _*_
"""Implementation, the medium result collected from ES server"""
from fhirpath.enums import FHIR_VERSION
from .base import Engine


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def create_engine():
    """ """
    engine = Engine(FHIR_VERSION.R4, None)
    return engine

def create_engine_from_context():
    """ """
