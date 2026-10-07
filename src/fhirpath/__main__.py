# _*_ coding: utf _*_
"""Command line interface: ``fhirpath`` / ``python -m fhirpath``.

Usage::

    fhirpath --version
    fhirpath --init-setup                  # R4 and STU3
    fhirpath --init-setup=R4,STU3
    fhirpath -I R4
"""
import sys
from typing import List, Optional

DEFAULT_RELEASES = ("R4", "STU3")


def _parse_releases(value: str) -> List[str]:
    from fhirpath.enums import FHIR_VERSION

    releases = [i.strip() for i in value.split(",") if i.strip()]
    for release in releases:
        if release not in FHIR_VERSION.__members__:
            raise ValueError(f"Unknown FHIR release '{release}'")
    return releases


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point; ``argv`` defaults to ``sys.argv``."""
    if argv is None:
        argv = sys.argv
    if len(argv) == 1:
        sys.stderr.write("At least one argument is required!\n")
        return 1

    command = argv[1]
    if command in ("-v", "--version"):
        import fhirpath

        sys.stdout.write(f"v{fhirpath.__version__}\n")
        return 0

    if command in ("-I", "--init-setup") or command.startswith("--init-setup="):
        try:
            if "=" in command:
                fhir_releases = _parse_releases(command.split("=", 1)[1])
            elif len(argv) > 2:
                fhir_releases = _parse_releases(argv[2])
            else:
                fhir_releases = list(DEFAULT_RELEASES)
        except ValueError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1
        if not fhir_releases:
            sys.stderr.write("No FHIR version has been provided.\n")
            return 1

        from fhirpath.search.fhirspec import FHIRSearchSpecFactory, FhirSpecFactory

        for rel in fhir_releases:
            FhirSpecFactory.from_release(rel)
            sys.stdout.write(
                f"FHIR Specification has been initiated for version {rel}\n"
            )

            FHIRSearchSpecFactory.from_release(rel)
            sys.stdout.write(
                f"FHIR Search Specification has been initiated for version {rel}\n"
            )
        return 0

    sys.stderr.write("Invalid argument has be provided.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
