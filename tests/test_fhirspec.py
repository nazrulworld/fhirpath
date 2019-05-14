# _*_ coding: utf-8 _*_
import pathlib
import shutil

import pytest

from fhirpath.fhirspec import FHIRSpec
from fhirpath.fhirspec import FhirSpecFactory
from fhirpath.fhirspec.downloader import download_and_extract
from fhirpath.thirdparty import attrdict
from fhirpath.utils import expand_path

from .fixtures import has_internet_connection


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

internet_conn_required = pytest.mark.skipif(
    not has_internet_connection(), reason="Internet Connection is required"
)


def ensure_spec_jsons(release):
    """ """
    directory = pathlib.Path(expand_path("${fhirpath}/fhirpath/fhirspec"))
    if not (directory / release).exists():
        if has_internet_connection():
            download_and_extract(release, str(directory))
        else:
            return False
    return True


def test_load_spec_json(fhir_spec_settings):
    """ """
    release = "R4"
    if not ensure_spec_jsons(release):
        pytest.skip("Internet Connection is required")

    source = "${fhirpath}/fhirpath/fhirspec/" + release
    settings = attrdict() + fhir_spec_settings
    spec = FHIRSpec(source, settings)
    assert spec.info.version == "4.0.0-a53ec6ee1b"


def test_fhirspec_creation_using_factory(fhir_spec_settings):
    """ """
    release = "R4"
    if not ensure_spec_jsons(release):
        pytest.skip("Internet Connection is required")

    spec = FhirSpecFactory.from_release(release, fhir_spec_settings)
    assert spec.info.version == "4.0.0-a53ec6ee1b"


@internet_conn_required
def test_fhir_spec_download_and_load():
    """ """
    directory = pathlib.Path(expand_path("${fhirpath}/fhirpath/fhirspec"))
    release = "STU3"
    if (directory / release).exists():
        shutil.rmtree((directory / release))

    spec = FhirSpecFactory.from_release(release)

    assert spec.info.version == "3.0.1.11917"
