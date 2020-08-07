# _*_ coding: utf-8 _*_
import logging
import pathlib
import shutil
import tempfile
import zipfile

from fhirspec import download

from fhirpath.enums import FHIR_VERSION

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.fhirspec.downloader")
BASE_URL = (
    "https://github.com/nazrulworld/fhirpath_helpers"
    "/raw/0.1.0/static/HL7/FHIR/spec/minified/{release}/{version}.zip"
)


def download_archive(
    release: FHIR_VERSION, temp_location: pathlib.Path
) -> pathlib.Path:
    """ """
    assert release != FHIR_VERSION.DEFAULT
    release_name = release.name
    version = release.value
    fullurl = BASE_URL.format(release=release_name, version=version)
    logger.info("Archive file has been downloaded from {0}".format(fullurl))
    return download(fullurl, temp_location)


def extract_spec_files(extract_location: pathlib.Path, archive_file: pathlib.Path):
    """ """
    with zipfile.ZipFile(str(archive_file), "r") as zip_ref:
        zip_ref.extractall(extract_location)


def download_and_extract(release: FHIR_VERSION, output_dir: pathlib.Path):
    """ """
    logger.info(
        "FHIR Resources Specification json files for release '{0}' version ´{1}´ "
        "are not found in local disk. "
        "Going to download...".format(release.name, release.value)
    )
    temp_dir = pathlib.Path(tempfile.mkdtemp())

    zip_file = download_archive(release, temp_dir)

    extract_spec_files(output_dir, zip_file)
    logger.info(
        "Downloaded archive has been extracted successfully, "
        "now all json files are available at {0}/{1}".format(output_dir, release.value)
    )
    # clean up
    shutil.rmtree(temp_dir)
