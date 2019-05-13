# _*_ coding: utf-8 _*_
import pytest

from fhirpath.fhirspec import DEFAULT_SETTINGS
from fhirpath.thirdparty import attrdict


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


@pytest.fixture
def response():
    """Sample pytest fixture.

    See more at: http://doc.pytest.org/en/latest/fixture.html
    """
    # import requests
    # return requests.get('https://github.com/audreyr/cookiecutter-pypackage')


@pytest.fixture(scope="module")
def fhir_spec_settings():
    """ """
    settings = attrdict(DEFAULT_SETTINGS.copy())

    yield settings
