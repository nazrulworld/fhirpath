# _*_ coding: utf-8 _*_
"""FHIR Specification: http://www.hl7.org/fhir/"""
import os
import pathlib
import typing

from fhirspec import FHIRSpec  # noqa: F401
from fhirspec import Configuration, FHIRStructureDefinition

from fhirpath.enums import FHIR_VERSION
from fhirpath.storage import FHIR_RESOURCE_SPEC_STORAGE, SEARCH_PARAMETERS_STORAGE

from .spec import (  # noqa: F401
    FHIRSearchSpec,
    ResourceSearchParameterDefinition,
    SearchParameter,
    logger,
    search_param_prefixes,
)

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


SPEC_JSON_DIR = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))


def ensure_spec_jsons(release: FHIR_VERSION):
    """ """
    release = FHIR_VERSION.normalize(release)
    version = release.value
    spec_dir = SPEC_JSON_DIR / release.name
    if not (spec_dir / version).exists():
        # Need download first
        if not spec_dir.exists():
            spec_dir.mkdir(parents=True)

        from .downloader import download_and_extract

        download_and_extract(release, spec_dir)


class FhirSpecFactory:
    """ """

    @staticmethod
    def from_release(release: str, config: Configuration = None):
        """ """
        release_enum = FHIR_VERSION[release]
        if release_enum == FHIR_VERSION.DEFAULT:
            release_enum = getattr(FHIR_VERSION, release_enum.value)
        version = release_enum.value
        src_dir = SPEC_JSON_DIR / release_enum.name / version
        ensure_spec_jsons(release_enum)
        from . import settings

        default_config = Configuration.from_module(settings)
        if config:
            default_config.update(config.as_dict())
        default_config.update({"FHIR_DEFINITION_DIRECTORY": src_dir})

        spec = FHIRSpec(default_config, src_dir)

        return spec


class FHIRSearchSpecFactory:
    """ """

    @staticmethod
    def from_release(release: str):
        """ """
        release_enum = FHIR_VERSION[release]
        if release_enum == FHIR_VERSION.DEFAULT:
            release_enum = getattr(FHIR_VERSION, release_enum.value)
        version = release_enum.value
        ensure_spec_jsons(release_enum)

        spec = FHIRSearchSpec(
            (SPEC_JSON_DIR / release_enum.name / version),
            release_enum,
            SEARCH_PARAMETERS_STORAGE,
        )
        return spec


def lookup_fhir_resource_spec(
    resource_type: typing.Text,
    cache: bool = True,
    fhir_release: FHIR_VERSION = FHIR_VERSION.DEFAULT,
) -> typing.Optional[FHIRStructureDefinition]:
    """

    :arg resource_type: the resource type name (required). i.e Organization

    :arg cache: (default True) the flag which indicates should query fresh or
        serve from cache if available.

    :arg fhir_release: FHIR Release (version) name.
        i.e FHIR_VERSION.STU3, FHIR_VERSION.R4

    :return FHIRStructureDefinition

    Example::

        >>> from fhirpath.fhirspec import lookup_fhir_resource_spec
        >>> from zope.interface import Invalid
        >>> dotted_path = lookup_fhir_resource_spec('Patient')
        >>> 'fhir.resources.patient.Patient' == dotted_path
        True
        >>> dotted_path = lookup_fhir_resource_spec('FakeResource')
        >>> dotted_path is None
        True
    """
    fhir_release = FHIR_VERSION.normalize(fhir_release)

    storage = FHIR_RESOURCE_SPEC_STORAGE.get(fhir_release.name)

    if storage.exists(resource_type) and cache:
        return storage.get(resource_type)

    specs = FhirSpecFactory.from_release(fhir_release.name)
    try:
        return specs.profiles[resource_type.lower()]
    except KeyError:
        logger.info(f"{resource_type} has not been found in profile specifications")
        return None
