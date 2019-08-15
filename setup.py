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


class PostIntsall(install):
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
    "Click>=6.0",
    "zope.interface>=4.6.0",
    "zope.component>=4.5",
    "multidict",
    "decorator",
    "fhir.resources>=5.0.1",
    "jsonpatch",
]

setup_requirements = ["pytest-runner"]

test_requirements = [
    "pytest",
    "guillotina>=4.8.13",
    "guillotina_elasticsearch",
    "pytest-docker-fixtures",
]
docs_requirements = [
    "sphinx",
    "sphinx-rtd-theme",
    "sphinxcontrib-httpdomain",
    "sphinxcontrib-httpexample",
]

setup(
    name="fhirpath",
    version="0.1.1",
    author="Md Nazrul Islam",
    author_email="email2nazrul@gmail.com",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description="FHIRPath implementation in Python.",
    entry_points={"console_scripts": ["fhirpath=fhirpath.cli:main"]},
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="fhirpath",
    packages=find_packages("src", include=["fhirpath"]),
    package_dir={"": "src"},
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    extras_require={
        "test": test_requirements + setup_requirements,
        "docs": docs_requirements,
    },
    url="https://github.com/nazrulworld/fhirpath",
    python_requires=", ".join((">=3.4", "<=3.8.*")),
    project_urls={
        "CI: Travis": "https://travis-ci.com/nazrulworld/fhirpath",
        "Coverage: codecov": "https://codecov.io/github/nazrulworld/fhirpath",
        "Docs: RTD": "https://fhirpath.readthedocs.io/",
        "GitHub: issues": "https://github.com/nazrulworld/fhirpath/issues",
        "GitHub: repo": "https://github.com/nazrulworld/fhirpath",
    },
    zip_safe=False,
    cmdclass={"install": PostIntsall, "develop": PostDevelop},
)
