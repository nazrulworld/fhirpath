=======
History
=======

0.10.5 (2020-12-17)
-------------------

Improvement

- ``BundleWrapper`` is providing two optional methods, ``calculate_fhir_base_url`` and ``resolve_absolute_uri`` and is now also taking optional parameter ``base_url``.


Fixes
- fixes ``ElasticSearchDialect.create_term`` [Kartik Sayani]

- fixes ``EngineResult.extract_references``. [Jason Paumier]

- fixes how composite search params are parsed. [Jason Paumier]

- Issue#28 `Nested GroupTerm search returns no matches <https://github.com/nazrulworld/fhirpath/issues/28>`_

- fixes ``SearchContext.normalize_param`` for composite search params [nazrulworld]

0.10.4 (2020-11-19)
-------------------

- fixes ``FHIRAbstractModel`` comparing at ``utils`` module for BundleWrapper.

- ``fallback_callable`` helper function is available at ``utils`` module.


0.10.3 (2020-11-17)
-------------------

Improvements

- More helper functions (``get_local_timezone``, ``timestamp_utc``, ``timestamp_utc``) are created.

- ``initial_bundle_data`` method is now available in Base Elasticsearch engine class,
  meaning that it is possible construct Bundle initial data into the derived class, so more flexibility.

Bugfixes

- Default bundle initial data was constructed ``meta.lastUpdated`` value with utc now time but without timezone offset, so
  during json serialization, timezone info was missed as a result reverse construct of Bundle complains validation error.

0.10.2 (2020-11-06)
-------------------

Improvements

- ``orjson`` is no longer required. ``json_dumps`` and ``json_loads`` now dynamically supports
  orjson and simplejson.


0.10.1 (2020-11-04)
-------------------

Bugfixes

- ``Connection.raw_connection`` was wrongly wrapped by ``AsyncElasticsearchConnection/ElasticsearchConnection.from_url()`` with self, instead of ``elasticsearch.AsyncElasticsearch/elasticsearch.Elasticsearch``'s instance.


0.10.0 (2020-11-04)
-------------------

Improvements


- Introducing `AsyncElasticsearchConnection`` and ``AsyncElasticsearchEngine`` the asyncio based connection and engine for Elasticsearch. See `Using Asyncio with Elasticsearch <https://elasticsearch-py.readthedocs.io/en/7.9.1/async.html>`_

- Added ``orjson`` based json serializer for Elasticsearch by default (when connection is made from connection factory).

- Added support for `_summary=text|data|count|true|false`. [arkhn]

- Added support for `_elements` search parameter. [arkhn]


Breaking

- ``async_result`` parameter is no longer needed for SearchContext, Search and Query (included async version) as from now all
  engine contains that information (``engine_class.is_async()``).

0.9.1 (2020-10-24)
------------------

- Added supports for ``_format`` and ``_pretty`` params, now there should no complain for those, instead of simply ignored. [nazrulworld]


0.9.0 (2020-10-24)
------------------

- Handle ``:identifier`` modifier for reference search parameters [simonvadee]

- fixes `BundleWrapper`` as_json mode, now includes with ``resourceType`` value. [nazrulworld]

- ``Dict`` response option has bee added in ``fhirpath.search.fhir_search`` [nazrulworld]

- Ignore empty search params #21 [simonvadee]

- Just for performance optimization issue minimum required ``zope.interface`` version is ``5.1.2``.

0.8.1 (2020-10-05)
------------------

- Disable pydantic validation for Bundle in fhirpath.utils.BundleWrapper [simonvadee]

- Two helper functions ``json_dumps`` and ``json_loads`` are now available under utils module [nazrulworld]

- Only apply search prefix on affected types #17 [simonvadee]

0.8.0 (2020-09-25)
------------------

Improvements

- add supports for some important FHIR search parameters (``_has``, ``_include`` and ``_revinclude``) [simonvadee]

- enable search on several resource types (_type search param) [Jasopaum]

- Issue #8 `Add search support for without any params or query string if context has resource type <https://github.com/nazrulworld/fhirpath/issues/8>`_ [nazrulworld]

- Issue #9 `multiple negative not working <https://github.com/nazrulworld/fhirpath/issues/9>`_ [nazrulworld]

Breaking

- ``fhirpath.search.SearchContext.resource_name`` has been changed ``fhirpath.search.SearchContext.resource_type`` and
  now datatype is List instead of string. Please check your API. [Jasopaum]

- For case of ``Elasticsearch`` based engine, you should use custom analyzer (``fhir_reference_analyzer``) for FHIR Reference type. For details see readme.


0.7.1 (2020-08-07)
------------------

- added missing ``isodate`` package dependency.


0.7.0 (2020-08-07)
------------------

Improvements

- Issue#5: Now ``ElasticsearchEngine::get_index_name`` takes one optional parameter ``resource_type``.

- Add supports for python version 3.6.

Breaking

- Make full capability with `fhir.resources <https://pypi.org/project/fhir.resources/>`_ version ``6.x.x``,
  please have a look of revolutionary changes of ``fhir.resources``.

0.6.2 (2020-06-30)
------------------

- ``fhirspec`` and ``fhir.resources`` versions are pinned.


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
