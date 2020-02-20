# -*- coding: utf-8 -*-
"""Top-level package for fhirpath."""


def get_version():
    """ """
    import os

    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.py"), "r"
    ) as fp:
        for line in fp:
            ln = line.strip()
            if not ln:
                continue
            if ln.startswith("version"):
                return eval(ln.split("=")[1].strip())


__author__ = """Md Nazrul Islam"""
__email__ = "email2nazrul@gmail.com"
__version__ = get_version()
