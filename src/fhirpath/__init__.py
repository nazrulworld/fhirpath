# -*- coding: utf-8 -*-
"""Top-level package for fhirpath."""


def __getattr__(name):
    """Lazy re-exports, so ``fhirpath.core`` can be used without the search stack."""
    if name == "FHIRPath":
        from .fhirpath import FHIRPath

        return FHIRPath
    if name == "Q_":
        from .search.query import Q_

        return Q_
    raise AttributeError("module %r has no attribute %r" % (__name__, name))


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
            if ln.startswith("__version__"):
                return eval(ln.split("=")[1].strip())


__author__ = """Md Nazrul Islam"""
__email__ = "email2nazrul@gmail.com"
__version__ = get_version()
