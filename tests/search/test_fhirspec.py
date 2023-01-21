# _*_ coding: utf-8 _*_
import os
import pathlib
import shutil

import pytest
from fhirspec import Configuration
from fhirspec import FHIRSpec

from fhirpath.enums import FHIR_VERSION
from fhirpath.search.fhirspec import FHIRSearchSpecFactory
from fhirpath.search.fhirspec import FhirSpecFactory
from fhirpath.search.fhirspec.downloader import download_and_extract
from fhirpath.search.storage import SEARCH_PARAMETERS_STORAGE

from .._utils import has_internet_connection


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


spec_directory = (
    pathlib.Path(os.path.dirname(os.path.abspath(__file__))).parent.parent
    / "src"
    / "fhirpath"
    / "search"
    / "fhirspec"
)


internet_conn_required = pytest.mark.skipif(
    not has_internet_connection(), reason="Internet Connection is required"
)


def ensure_spec_jsons(release_name):
    """ """
    release = getattr(FHIR_VERSION, release_name)
    spec_dir = spec_directory / release.name
    if not spec_dir.exists():
        spec_dir.mkdir()

    if not (spec_dir / release.value).exists():
        if has_internet_connection():
            download_and_extract(release, spec_dir)
        else:
            return False
    return True


def test_load_spec_json(fhir_spec_settings):
    """ """
    release = FHIR_VERSION["R4"]
    if not ensure_spec_jsons(release.name):
        pytest.skip("Internet Connection is required")

    source = spec_directory / release.name / release.value
    settings = fhir_spec_settings.as_dict()
    settings.update({"FHIR_DEFINITION_DIRECTORY": source})

    spec = FHIRSpec(Configuration(settings), source)
    assert spec.info.version_raw == "4.0.1-9346c8cc45"


def test_fhirspec_creation_using_factory(fhir_spec_settings):
    """ """
    release_name = "R4"
    if not ensure_spec_jsons(release_name):
        pytest.skip("Internet Connection is required")

    spec = FhirSpecFactory.from_release(release_name, fhir_spec_settings)
    assert spec.info.version_raw == "4.0.1-9346c8cc45"


@internet_conn_required
def test_fhir_spec_download_and_load():
    """ """
    release = FHIR_VERSION["STU3"]
    spec_dir = spec_directory / release.name
    if not spec_dir.exists():
        spec_dir.mkdir()
    if (spec_dir / release.value).exists():
        shutil.rmtree((spec_dir / release.value))

    spec = FhirSpecFactory.from_release(release.name)

    assert spec.info.version_raw == "3.0.2.11917"


def test_fhir_search_spec():
    """ """
    release = "R4"
    if not ensure_spec_jsons(release):
        pytest.skip("Internet Connection is required")

    storage = SEARCH_PARAMETERS_STORAGE.get(release)

    assert storage.empty()

    spec = FHIRSearchSpecFactory.from_release(release)
    spec.write()

    resource_search_params = storage.get("Resource")
    assert resource_search_params._id.expression == "Resource.id"

    patient_params = storage.get("Patient")

    for param in resource_search_params:
        assert param in patient_params
    encounter_params = storage.get("Encounter")

    assert "length" in encounter_params

    for param in resource_search_params:
        assert param in encounter_params


def test_lookup_fhir_resource_spec():
    """ """
    from fhirpath.search.fhirspec import lookup_fhir_resource_spec
    from fhirspec import FHIRStructureDefinition

    spec = lookup_fhir_resource_spec("Patient", False, FHIR_VERSION.R4)
    assert spec is not None
    assert isinstance(spec, FHIRStructureDefinition)

    spec = lookup_fhir_resource_spec("PatientFake", False, FHIR_VERSION.R4)
    assert spec is None
