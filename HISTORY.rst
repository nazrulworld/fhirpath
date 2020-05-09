=======
History
=======

0.6.1 (2020-05-09)
------------------
A must update release (from ``0.6.0``)!

Bugfixes

- fix: issues, those arieses due to fix bellow issue.
- fix: ``fhirpath.storage.FHIR_RESOURCE_CLASS_STORAGE``, ``fhirpath.storage.PATH_INFO_STORAGE``, ``fhirpath.storage.SEARCH_PARAMETERS_STORAGE`` and ``fhirpath.storage.FHIR_RESOURCE_SPEC_STORAGE`` took wrong FHIR release as keys.


0.6.0 (2020-05-08)
------------------

Breaking

- Hard dependency on `fhirspec <https://pypi.org/project/fhirspec/>`_.
- Minimum python version 3.7 is required.
- Minimum required ``fhir.resources`` version is now ``5.1.0`` meaning FHIR R4 4.0.1 and STU3 3.0.2.
  Please follow changes log https://pypi.org/project/fhir.resources/5.1.0/.



0.5.1 (2020-03-18)
------------------

New features

- ``__main__`` module has been created, now possible to see version and/or initiated required FHIR versions.
  For example ``python -m "fhirpath" --version``, ``python -m "fhirpath" --init-setup`` [nazrulworld]

Improvements

- Updated fix version of elasticsearch mappings.


0.5.0 (2020-03-11)
------------------

New Features

- ``FHIRPath`` (Normative Release) support available. A dedicated class is now available ```fhirpath.FHIRPath``,
  although it is working in progress (meaning that many methods/functions are yet to do complete.)

Improvements

- Add support for important FHIR search modifier ``:contains``. See https://github.com/nazrulworld/fhirpath/issues/1

- Add support for ``:above``FHIR search modifier and `èb`` prefix. See https://github.com/nazrulworld/fhirpath/issues/2

- Add support for ``:bellow`` FHIR search modifier and ``sa`` prefix. See https://github.com/nazrulworld/fhirpath/issues/2


Bugfixes

- Upgrade to this version is recommended as it includes couples of major bug fixes.


Breaking

- The ``fhirpath.navigator`` module has been removed and introduced new module ``fhirpath.model``.
  ``fhirpath.utils.Model`` has been moved to `fhirpath.model``.


0.4.1 (2019-11-05)
------------------

Bugfixes

- ``fhirpath.search.Search.parse_query_string`` now returning ``MuliDict``(what is expected) instead of ``MultiDictProxy``.


0.4.0 (2019-10-24)
------------------

Improvements

- Now full ``select`` features are accepted, meaning that you can provide multiple path in ``select`` section. for example ``select(Patient.name, Patient.gender)``.

- FHIRPath ``count()`` and ``empty()`` functions are supported.

- Supports path navigation with index and functions inside ``select``. Example ``[index]``, ``last()``, ``first()``, ``Skip()``, ``Take()``, ``count()``.

Breakings

- ``QueryResult.first`` and ``QueryResult.single`` are no longer return FHIR Model instance instead returning ``fhirpath.engine.EngineResultRow``.

- ``QueryResult.fetchall`` returning list of ``fhirpath.engine.EngineResultRow`` instead of FHIR JSON.

- ``QueryResult`` iteration returning list of FHIR Model instance on condition (if select is `*`), other than returning list of ``fhirpath.engine.EngineResultRow``.


0.3.1 (2019-10-08)
------------------

Improvements

- Add support for search parameter expression that contains with space+as (``MedicationRequest.medication as CodeableConcept``)

Bugfixes

- ``not`` modifier is now working for ``Coding`` and ``CodeableConcept``.

- "ignore_unmapped" now always True in case of nested query.

- "unmapped_type" now set explicitly long value. See related issue https://stackoverflow.com/questions/17051709/no-mapping-found-for-field-in-order-to-sort-on-in-elasticsearch


0.3.0 (2019-09-30)
------------------

Improvements

- Supports multiple AND values for same search parameter!.

- Add support FHIR version ``STU3`` compability for Money type search.[nazrulworld]

- IN Query support added.[nazrulworld]

- Support PathElement that contains string path with .as(), thus suports for Search also.

- Supports ``Duration`` type in Search.

- Add support ``composite`` type search param.


Bugfixes

- Multiple search values (IN search)

- Missing ``text`` for HumanName and Address search.



0.2.0 (2019-09-15)
------------------

Breakings:

- Built-in providers ( ``guillotina_app`` and ``plone_app`` ) have been wiped as both becoming separate pypi project.

- ``queries`` module has been moved from ``fql`` sub-package to fhirpath package and also renamed as ``query``.


Improvements:

- There are so many improvements made for almost all most modules.

- FhirSearch coverages are increased.

- Sort, Limit facilities added in Query as well in FhirSearch.


Bugfixes:

- numbers of bugs fixed.



0.1.1 (2019-08-15)
------------------

- First working version has been released. Of-course not full featured.


0.1.0 (2018-12-15)
------------------

* First release on PyPI.(Just register purpose, not usable at all, next release coming soon)
