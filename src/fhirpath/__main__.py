# _*_ coding: utf _*_
import sys


def main(argv):
    """ """
    if len(argv) == 1:
        sys.stderr.write("At least one argument is required!\n")
        return 1

    import fhirpath
    from fhirpath.enums import FHIR_VERSION
    from fhirpath.fhirspec import FHIRSearchSpecFactory, FhirSpecFactory

    if argv[1] in ("-v", "--version"):
        sys.stdout.write(f"v{fhirpath.__version__}\n")
    elif argv[1] in ("-I", "--init-setup"):
        fhir_releases = ("R4", "STU3")
        if len(argv) == 3:
            if argv[2].startswith("--init-setup="):
                fhir_releases = [
                    i.strip()
                    for i in argv[2].split("=")[1].split(",")
                    if FHIR_VERSION[i.strip()]
                ]
        elif len(argv) == 4:
            fhir_releases = [
                i.strip() for i in argv[2].split(",") if FHIR_VERSION[i.strip()]
            ]
        if not fhir_releases:
            sys.stderr.write("No FHIR version has been provided.\n")
            return 1

        for rel in fhir_releases:
            FhirSpecFactory.from_release(rel)
            sys.stdout.write(
                f"FHIR Specification has been initiated for version {rel}\n"
            )

            FHIRSearchSpecFactory.from_release(rel)
            sys.stdout.write(
                f"FHIR Search Specification has been initiated for version {rel}\n"
            )

    else:
        sys.stderr.write("Invalid argument has be provided.\n")
        return 1
    return 0


if __name__ == "__main__":
    main(sys.argv)
