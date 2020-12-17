#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import find_packages
from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def run_post_install(self):
    """ """


def run_post_develop(self):
    """ """
    run_post_install(self)


class PostInstall(install):
    """ """

    def run(self):
        """ """
        install.run(self)
        # Run custom post install
        run_post_install(self)


class PostDevelop(develop):
    """ """

    def run(self):
        """ """
        develop.run(self)
        # run custom develop
        run_post_develop(self)


with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

requirements = [
    "zope.interface>=5.1.2",
    "multidict",
    "fhirspec>=0.2.5",
    "fhir.resources>=6.0.0,<7.0",
    "yarl",
    "isodate",
]

setup_requirements = ["pytest-runner", "setuptools_scm[toml]", "wheel"]

test_requirements = [
    "more-itertools",
    "pytest>=6.0.1",
    "pytest-cov",
    "pytest-mock",
    "pytest-asyncio",
    "pytest-docker-fixtures",
    "psycopg2",
    "elasticsearch[async]>7.8.0,<8.0.0",
    "SQLAlchemy",
    "pytz",
    "mypy",
    "requests==2.23.0",
    "flake8==3.8.3",
    "flake8-isort==3.0.0",
    "flake8-bugbear==20.1.4",
    "isort==4.3.21",
    "black",
]
docs_requirements = [
    "sphinx",
    "sphinx-rtd-theme",
    "sphinxcontrib-httpdomain",
    "sphinxcontrib-httpexample",
]

development_requirements = [
    "Jinja2==2.11.1",
    "MarkupSafe==1.1.1",
    "colorlog==2.10.0",
    "certifi",
    "orjson",
    "zest-releaser[recommended]",
]

setup(
    name="fhirpath",
    version="0.10.5.dev0",
    author="Md Nazrul Islam",
    author_email="email2nazrul@gmail.com",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Typing :: Typed",
    ],
    description="FHIRPath implementation in Python.",
    entry_points={"console_scripts": ["fhirpath=fhirpath.cli:main"]},
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="fhirpath, HL7, FHIR, healthcare",
    packages=find_packages("src", include=["fhirpath"]),
    package_dir={"": "src"},
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    extras_require={
        "test": test_requirements + setup_requirements,
        "docs": docs_requirements,
        "all": test_requirements
        + setup_requirements
        + docs_requirements
        + development_requirements,
    },
    url="https://nazrul.me/fhirpath/",
    python_requires=", ".join((">=3.6",)),
    project_urls={
        "CI: Travis": "https://travis-ci.org/nazrulworld/fhirpath",
        "Coverage: codecov": "https://codecov.io/github/nazrulworld/fhirpath",
        "Docs: RTD": "https://fhirpath.readthedocs.io/",
        "GitHub: issues": "https://github.com/nazrulworld/fhirpath/issues",
        "GitHub: repo": "https://github.com/nazrulworld/fhirpath",
    },
    zip_safe=False,
    cmdclass={"install": PostInstall, "develop": PostDevelop},
)
