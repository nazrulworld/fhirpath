# _*_ coding: utf-8 _*_
import io
import logging
import pathlib
import shutil
import tempfile
import zipfile
from ast import literal_eval
from http.client import HTTPResponse
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request
from urllib.request import urlopen

from fhirpath.enums import FHIR_VERSION


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.fhirspec.downloader")
BASE_URL = (
    "https://github.com/nazrulworld/fhirpath_helpers"
    "/raw/master/static/HL7/FHIR/spec/minified/{release}/{version}.zip"
)


def parse_filename(response: HTTPResponse) -> str:
    """ """

    def _from_url(url: str):
        path_ = urlparse(url).path
        return pathlib.Path(path_).name

    content_type = response.headers.get("Content-Type", "")
    if content_type.startswith("text/"):
        return _from_url(response.geturl())
    file_info = response.headers.get("Content-Disposition", "")
    for part in file_info.split(";"):
        part_ = part.strip()
        if not part_:
            continue
        if part_.lower().startswith("filename="):
            filename = part_.split("=", 1)[1].strip()
            try:
                # try escape " or '
                filename = literal_eval(filename)
            except ValueError:
                # It's OK
                pass
            return filename
    # always fall-back
    return _from_url(response.geturl())


def write_stream(output_dir: pathlib.Path, response: HTTPResponse) -> pathlib.Path:
    """ """
    filename = parse_filename(response)
    filename_location = output_dir / filename
    with io.open(str(filename_location), "wb") as fp:

        while not response.closed:
            chunk = response.read(io.DEFAULT_BUFFER_SIZE)
            if not chunk:
                break
            fp.write(chunk)
    return filename_location


def download_archive(
    release: FHIR_VERSION, temp_location: pathlib.Path
) -> pathlib.Path:
    """ """
    assert release != FHIR_VERSION.DEFAULT
    release_name = release.name
    version = release.value
    fullurl = BASE_URL.format(release=release_name, version=version)

    request = Request(url=fullurl, method="GET", unverifiable=False)

    response: HTTPResponse
    try:
        response = urlopen(request)
        assert response.status == 200
    except HTTPError:
        # xxx: handle nicely later
        raise
    logger.info("Archive file has been downloaded from {0}".format(fullurl))
    return write_stream(temp_location, response)


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
