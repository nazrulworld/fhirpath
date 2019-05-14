# _*_ coding: utf-8 _*_
import io
import logging
import os
import shutil
import tempfile
import zipfile
from http.client import HTTPResponse
from urllib.error import HTTPError
from urllib.request import Request
from urllib.request import urlopen

from fhirpath.enums import FHIR_VERSION


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.fhirspec.downloader")
BASE_URL = (
    "https://github.com/nazrulworld/fhirpath-scripts/blob/master/resources"
    "/fhirspec/{release}.zip?raw=true"
)


def write_stream(outputdir: str, response: HTTPResponse, release: FHIR_VERSION):
    """ """
    filename = ".".join([release.value, "zip"])

    with io.open(os.path.join(outputdir, filename), "wb") as fp:

        while not response.closed:
            chunk = response.read(io.DEFAULT_BUFFER_SIZE)
            if not chunk:
                break

            fp.write(chunk)
    return os.path.join(outputdir, filename)


def download_archive(release: FHIR_VERSION, temp_location: str):
    """ """
    fullurl = BASE_URL.format(release=release.value)

    request = Request(url=fullurl, method="GET", unverifiable=False)

    response: HTTPResponse = None
    try:
        response = urlopen(request)
        assert response.status == 200
    except HTTPError:
        # xxx: handle nicely later
        raise
    logger.info("Archive file has been downloaded from {0}".format(fullurl))
    return write_stream(temp_location, response, release)


def extract_spec_files(extract_location, archive_file):
    """ """
    with zipfile.ZipFile(str(archive_file), "r") as zip_ref:
        zip_ref.extractall(extract_location)


def download_and_extract(release: FHIR_VERSION, output_dir: str):
    """ """
    logger.info(
        "FHIR Resources Specification json files for release '{0}' "
        "are not found in local disk. "
        "Going to download...".format(release.value)
    )
    temp_dir = tempfile.mkdtemp()

    zip_file = download_archive(release, temp_dir)

    extract_spec_files(output_dir, zip_file)
    logger.info(
        "Downloaded archive has been extracted successfully, "
        "now all json files are available at {0}/{1}".format(output_dir, release.value)
    )
    # clean up
    shutil.rmtree(temp_dir)
