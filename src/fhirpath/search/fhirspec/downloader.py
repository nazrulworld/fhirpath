# _*_ coding: utf-8 _*_
"""Fetch the FHIR definition files a release needs, straight from HL7.

Every release publishes ``https://hl7.org/fhir/<release>/definitions.json.zip``
(STU3, R4, R4B, R5). The archive is reduced to the four files this package reads,
minified the same way for every release, into ``<release>/<version>/``::

    search-parameters.json        SearchParameter bundle (unchanged)
    profiles-resources.min.json   StructureDefinitions, without snapshot and text
    profiles-types.min.json       StructureDefinitions, without snapshot and text
    valuesets.min.json            ValueSets and CodeSystems, without text
    version.info                  release information (generated when missing)
"""

import json
import logging
import pathlib
import shutil
import tempfile
import zipfile
from typing import Any, Dict

from fhirspec import download

from fhirpath.enums import FHIR_VERSION

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"

logger = logging.getLogger("fhirpath.fhirspec.downloader")
BASE_URL = "https://hl7.org/fhir/{release}/definitions.json.zip"

SEARCH_PARAMETERS_FILE = "search-parameters.json"
VERSION_INFO_FILE = "version.info"
# version.info of the official build, for archives that do not include it
KNOWN_VERSION_INFO = {
    "STU3": (
        "[FHIR]\nFhirVersion=3.0.2.11917\nversion=3.0.2\n"
        "revision=11917\ndate=20170419074443\n"
    ),
}
# archive member -> local file
MINIFIED_FILES = {
    "profiles-resources.json": "profiles-resources.min.json",
    "profiles-types.json": "profiles-types.min.json",
    "valuesets.json": "valuesets.min.json",
}


def download_archive(
    release: FHIR_VERSION, temp_location: pathlib.Path
) -> pathlib.Path:
    """ """
    assert release != FHIR_VERSION.DEFAULT
    fullurl = BASE_URL.format(release=release.name)
    logger.info("Downloading FHIR definitions archive from {0}".format(fullurl))
    return download(fullurl, temp_location)


def minify_profiles(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the StructureDefinitions only, without their snapshot and narrative
    (the differential is all ``fhirspec`` needs)."""
    entries = []
    for entry in bundle.get("entry", []):
        resource = entry["resource"]
        if resource.get("resourceType") != "StructureDefinition":
            continue
        resource = {
            key: value
            for key, value in resource.items()
            if key not in ("snapshot", "text")
        }
        entries.append({"fullUrl": entry.get("fullUrl"), "resource": resource})
    return dict(bundle, entry=entries)


def minify_valuesets(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """ValueSets and CodeSystems without their narrative."""
    entries = []
    for entry in bundle.get("entry", []):
        resource = {
            key: value for key, value in entry["resource"].items() if key != "text"
        }
        entries.append({"fullUrl": entry.get("fullUrl"), "resource": resource})
    return dict(bundle, entry=entries)


MINIFIERS = {
    "profiles-resources.json": minify_profiles,
    "profiles-types.json": minify_profiles,
    "valuesets.json": minify_valuesets,
}


def _write_json(path: pathlib.Path, data: Dict[str, Any]):
    with open(str(path), "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, separators=(",", ":"))


def extract_spec_files(
    extract_location: pathlib.Path, archive_file: pathlib.Path, release: FHIR_VERSION
):
    """Extract and minify the definition files of ``archive_file`` into
    ``extract_location/<version>``. Archive members are matched by file name, as
    some releases put them in a ``definitions.json/`` folder."""
    members: Dict[str, str] = {}
    with zipfile.ZipFile(str(archive_file), "r") as zip_ref:
        for name in zip_ref.namelist():
            members.setdefault(pathlib.PurePosixPath(name).name, name)

        wanted = [SEARCH_PARAMETERS_FILE, *MINIFIED_FILES]
        missing = [name for name in wanted if name not in members]
        if missing:
            raise FileNotFoundError(
                f"FHIR {release.name} definitions archive misses {', '.join(missing)}"
            )

        # build in a sibling folder and move it in place at the end, so that an
        # interrupted download never leaves a half-written release behind
        target = extract_location / release.value
        work = pathlib.Path(tempfile.mkdtemp(dir=str(extract_location)))
        try:
            with (
                zip_ref.open(members[SEARCH_PARAMETERS_FILE]) as src,
                open(str(work / SEARCH_PARAMETERS_FILE), "wb") as dst,
            ):
                shutil.copyfileobj(src, dst)

            for name, local_name in MINIFIED_FILES.items():
                with zip_ref.open(members[name]) as src:
                    bundle = json.load(src)
                _write_json(work / local_name, MINIFIERS[name](bundle))

            if VERSION_INFO_FILE in members:
                with (
                    zip_ref.open(members[VERSION_INFO_FILE]) as src,
                    open(str(work / VERSION_INFO_FILE), "wb") as dst,
                ):
                    shutil.copyfileobj(src, dst)
            else:
                # the STU3 archive has none
                (work / VERSION_INFO_FILE).write_text(
                    KNOWN_VERSION_INFO.get(
                        release.name,
                        "[FHIR]\nFhirVersion={0}\nversion={0}\n".format(release.value),
                    ),
                    encoding="utf-8",
                )

            if target.exists():
                shutil.rmtree(str(target))
            work.rename(target)
        finally:
            if work.exists():
                shutil.rmtree(str(work))


def download_and_extract(release: FHIR_VERSION, output_dir: pathlib.Path):
    """ """
    logger.info(
        "FHIR Resources Specification json files for release '{0}' version ´{1}´ "
        "are not found in local disk. "
        "Going to download...".format(release.name, release.value)
    )
    temp_dir = pathlib.Path(tempfile.mkdtemp())
    try:
        zip_file = download_archive(release, temp_dir)
        extract_spec_files(output_dir, zip_file, release)
    finally:
        # clean up
        shutil.rmtree(str(temp_dir))
    logger.info(
        "Downloaded archive has been extracted successfully, "
        "now all json files are available at {0}/{1}".format(output_dir, release.value)
    )
