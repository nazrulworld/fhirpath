# _*_ coding: utf-8 _*_
"""Command line interface (``fhirpath`` / ``python -m fhirpath``)."""
import subprocess
import sys

import fhirpath
from fhirpath.__main__ import main

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


def test_version(capsys):
    assert main(["fhirpath", "--version"]) == 0
    assert capsys.readouterr().out == f"v{fhirpath.__version__}\n"
    assert main(["fhirpath", "-v"]) == 0


def test_version_comes_from_package_metadata():
    from importlib.metadata import version

    assert fhirpath.__version__ == version("fhirpath")


def test_argument_errors(capsys):
    assert main(["fhirpath"]) == 1
    assert main(["fhirpath", "--nope"]) == 1
    assert main(["fhirpath", "--init-setup=R9"]) == 1
    assert "Unknown FHIR release 'R9'" in capsys.readouterr().err
    assert main(["fhirpath", "-I", ""]) == 1


def test_init_setup(capsys):
    assert main(["fhirpath", "--init-setup=R4"]) == 0
    assert main(["fhirpath", "-I", "STU3"]) == 0
    out = capsys.readouterr().out
    assert "FHIR Specification has been initiated for version R4" in out
    assert "FHIR Search Specification has been initiated for version STU3" in out


def test_python_dash_m():
    result = subprocess.run(
        [sys.executable, "-m", "fhirpath", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout == f"v{fhirpath.__version__}\n"
