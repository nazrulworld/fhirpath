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
    """Version of the installed distribution (``project.version`` in pyproject.toml)."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("fhirpath")
    except PackageNotFoundError:
        # running from a source tree that is not installed
        return "0.0.0.dev0"


__author__ = """Md Nazrul Islam"""
__email__ = "email2nazrul@gmail.com"
__version__ = get_version()
