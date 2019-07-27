# -*- coding: utf-8 -*-
from guillotina import configure


__author__ = """Md Nazrul Islam"""
__email__ = "email2nazrul@gmail.com"

app_settings = {
    # provide custom application settings here...
}


def includeme(root):
    """ """
    configure.scan("fhirpath.providers.guillotina_app.field")
    configure.scan("fhirpath.providers.guillotina_app.utilities")
