============
Introduction
============

.. image:: https://img.shields.io/travis/com/nazrulworld/fhirpath.svg
        :target: https://travis-ci.com/nazrulworld/fhirpath

.. image:: https://readthedocs.org/projects/fhirpath/badge/?version=latest
        :target: https://fhirpath.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://codecov.io/gh/nazrulworld/fhirpath/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/nazrulworld/fhirpath/branch/master
   :alt: Test Coverage

.. image:: https://img.shields.io/pypi/pyversions/fhirpath.svg
   :target: https://pypi.python.org/pypi/fhirpath/
   :alt: Python Versions

.. image:: https://img.shields.io/lgtm/grade/python/g/nazrulworld/fhirpath.svg?logo=lgtm&logoWidth=18
    :target: https://lgtm.com/projects/g/nazrulworld/fhirpath/context:python
    :alt: Language grade: Python

.. image:: https://img.shields.io/pypi/v/fhirpath.svg
   :target: https://pypi.python.org/pypi/fhirpath

.. image:: https://img.shields.io/pypi/l/fhirpath.svg
   :target: https://pypi.python.org/pypi/fhirpath/
   :alt: License

.. image:: https://static.pepy.tech/personalized-badge/fhirpath?period=total&units=international_system&left_color=black&right_color=green&left_text=Downloads
    :target: https://pepy.tech/project/fhirpath
    :alt: Downloads

.. image:: https://www.hl7.org/fhir/assets/images/fhir-logo-www.png
        :target: https://www.hl7.org/fhir/fhirpath.html
        :alt: HL7® FHIR®

FHIRPath_ (v3.0.0, including the FHIR®-specific extensions) implementation in Python,
along side it provides support for `FHIR Search <https://www.hl7.org/fhir/search.html>`_ API and
Query (we called it ``fql(FHIR Query Language)``)
API to fetch FHIR resources from any data-source(database).
This library is built in ORM_ like approach. Our goal is to make 100% (as much as possible)
FHIRPath_ specification compliance product.

* Evaluates FHIRPath expressions against FHIR® resources: passes 1061 of the 1064 runnable
  cases of the official FHIRPath conformance test suite (see `Evaluating FHIRPath expressions`_).
* Supports FHIR® ``STU3`` and ``R4``.
* Supports multiple provider´s engine. Now Plone_ & guillotina_ framework powered providers `fhirpath-guillotina`_ and `collective.fhirpath`_ respectively are supported and more coming soon.
* Supports multiple dialects, for example elasticsearch_, GraphQL_, PostgreSQL_. Although now elasticsearch_ has been supported.
* Provide full support of `FHIR Search <https://www.hl7.org/fhir/search.html>`_ with easy to use API.


Evaluating FHIRPath expressions
-------------------------------

The ``fhirpath.core`` package is a complete FHIRPath_ 3.0.0 engine. It needs no
database: give it a resource and an expression.

Resources can be ``fhir.resources`` model instances or plain JSON dicts (load JSON with
``json.loads(text, parse_float=decimal.Decimal)`` to keep decimal precision)::

    >>> patient = {
    ...     "resourceType": "Patient",
    ...     "id": "example",
    ...     "active": True,
    ...     "gender": "male",
    ...     "birthDate": "1974-12-25",
    ...     "name": [
    ...         {"use": "official", "family": "Chalmers", "given": ["Peter", "James"]},
    ...         {"use": "usual", "given": ["Jim"]},
    ...     ],
    ...     "telecom": [{"system": "phone", "value": "(03) 5555 6473", "use": "work"}],
    ... }

Evaluate an expression
~~~~~~~~~~~~~~~~~~~~~~

``evaluate(resource, expression)`` always returns a list (a FHIRPath collection)::

    >>> from fhirpath.core import evaluate
    >>> evaluate(patient, "name.where(use = 'official').given")
    ['Peter', 'James']
    >>> evaluate(patient, "name.given.count()")
    [3]
    >>> evaluate(patient, "Patient.name.select(given.first() + ' ' + family)")
    ['Peter Chalmers']
    >>> evaluate(patient, "birthDate < @2000-01-01")
    [True]
    >>> evaluate(patient, "name.exists(use = 'nickname')")
    [False]
    >>> evaluate(patient, "deceased")
    []

The same works with a model instance::

    >>> from fhir.resources.patient import Patient
    >>> evaluate(Patient.model_validate(patient), "name.given.first()")
    ['Peter']

Results are plain Python values:

* FHIR primitives become FHIRPath System values: ``str``, ``bool``, ``int``, ``Decimal``,
  ``fhirpath.core.Long``, ``FPDate``/``FPDateTime``/``FPTime`` (dates and times keep their
  partial precision, ``str(value)`` gives the ISO text) and ``fhirpath.core.Quantity``.
* Complex elements (``HumanName``, a contained resource, …) are returned as they appear in
  the input: the model object, or the dict.

Quantities and units (UCUM and calendar durations) are supported::

    >>> evaluate(None, "1 'kg' = 1000 'g'")
    [True]
    >>> evaluate(None, "(4 days + 2 'wk').toString()")
    ['18 days']

Compile once, evaluate many times
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``compile()`` parses the expression once. ``test()`` evaluates it as a predicate
(an invariant): a single Boolean is returned as is, otherwise "is the result non-empty"::

    >>> from fhirpath.core import compile
    >>> invariant = compile("name.where(use = 'official').exists() implies birthDate.exists()")
    >>> invariant.test(patient)
    True
    >>> invariant.evaluate(patient)
    [True]

Variables, references and other options
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pass ``%variables`` as a dict. ``%resource``, ``%rootResource``, ``%context``, ``%ucum``,
``%sct``, ``%loinc`` and :literal:`%\`vs-[id]\``/:literal:`%\`ext-[id]\`` are always available::

    >>> evaluate(patient, "%minimum + 1", {"minimum": 5})
    [6]
    >>> evaluate(patient, "%resource.id")
    ['example']

``resolve()`` finds contained resources (``#id``) and Bundle entries by itself. Anything
else (``Patient/123``, absolute URLs) goes to a ``resolver`` you provide::

    >>> def resolver(reference, origin):
    ...     # return a model instance or dict, or None when unknown
    ...     return {"resourceType": "Organization", "id": "1", "name": "ACME"}
    >>> evaluate(
    ...     {"resourceType": "Patient", "managingOrganization": {"reference": "Organization/1"}},
    ...     "managingOrganization.resolve().name",
    ...     resolver=resolver,
    ... )
    ['ACME']

Other keyword options of ``evaluate()``, ``CompiledExpression.evaluate()`` and ``FHIRPath()``:

* ``terminology``: an object implementing ``fhirpath.core.Terminology``
  (``member_of``/``subsumes``) for ``memberOf()``, ``subsumes()`` and ``subsumedBy()``.
* ``tracer``: ``callable(name, values)`` receiving ``trace()`` output (default: the
  ``fhirpath.trace`` logger at DEBUG level).
* ``now``: an ``FPDateTime`` used by ``now()``/``today()``/``timeOfDay()`` (useful in tests).
* ``nodes=True`` (``evaluate()`` only): return the engine's ``Node`` objects, which carry the
  FHIR type, element path (``node.path()``) and parent, instead of plain values.

Errors
~~~~~~

Every FHIRPath error raises ``fhirpath.core.EvaluationError``. Invalid syntax raises its
subclass ``FHIRPathSyntaxError``::

    >>> from fhirpath.core import EvaluationError
    >>> try:
    ...     evaluate(patient, "name.given + ' x'")  # '+' needs single items, given has 3
    ... except EvaluationError as error:
    ...     print(error.msg)
    left operand of '+' must be a single item, got 3

Fluent API
~~~~~~~~~~

``fhirpath.FHIRPath`` wraps the same engine in a chainable Python API. Attribute access
navigates elements and calling an attribute invokes the FHIRPath function of that name::

    >>> from fhirpath import FHIRPath
    >>> fp = FHIRPath(patient)
    >>> fp.name.where("use = 'official'").given.to_list()
    ['Peter', 'James']
    >>> fp.name.first().family.upper().to_list()
    ['CHALMERS']
    >>> fp.name[1].given.to_list()
    ['Jim']
    >>> bool(fp.active)
    True

* Arguments of ``where``, ``select``, ``exists``, ``all``, ``repeat``, ``sort``, ``iif``,
  ``coalesce``, ``aggregate`` and the type argument of ``ofType``/``is_``/``as_`` are
  FHIRPath expression strings. Any other argument is a value: a Python value becomes a
  literal, a ``FHIRPath`` or list is passed as a collection, and ``Expr("…")`` marks an
  expression explicitly::

    >>> from fhirpath.fhirpath import Expr
    >>> fp.name.given.combine(Expr("name.family")).to_list()
    ['Peter', 'James', 'Jim', 'Chalmers']
    >>> fp.gender.is_("code").to_list()
    [True]

* ``is_()``, ``as_()`` and ``not_()`` stand for the keyword-named functions; use
  ``fp["class"]`` for element names that are Python keywords.
* ``fp.evaluate("…")`` evaluates an expression with the current collection as input.
* Results: ``to_list()``, iteration, ``len()``, ``bool()``; ``to_nodes()`` for ``Node`` objects.

Specification notes
~~~~~~~~~~~~~~~~~~~

* Implements FHIRPath 3.0.0 (including the STU parts: ``Long``, ``sort()``, instance
  selectors, ``defineVariable()``, ``lowBoundary()``/``highBoundary()``, ``duration()``,
  aggregates, …) and the FHIR additions (``resolve()``, ``extension()``, ``hasValue()``,
  ``getValue()``, ``htmlChecks()``, ``conformsTo()`` for core profiles, …).
* ``elementDefinition()``, ``slice()`` and ``weight()`` need a validator or profile store
  and raise an error.
* Typed choice names (``Observation.valueQuantity``) are accepted next to the standard
  ``Observation.value`` (lenient mode, as in fhirpath.js).
* Unit conversion uses a built-in subset of UCUM (common clinical, SI and customary units).


Usages
------

This library is kind of abstract type, where all specifications from FHIRPath_ Normative Release (v2.0.0) are implemented rather than completed solution (ready to go).
The main reason behind this design pattern, to support multiple database systems as well as well as any framework, there is no dependency.

``fhirpath`` never taking care of creating indexes, mappings (elasticsearch) and storing data, if you want to use this library, you have to go
through any of existing providers (see list bellow) or make your own provider (should not too hard work).


Simple example
~~~~~~~~~~~~~~

Assumption:

1. Elasticsearch server 7.x.x Installed.

2. Mappings and indexes are handled manually.

3. Data (document) also are stored manually.


Create Connection and Engine::

    >>> from fhirpath.connectors import create_connection
    >>> from fhirpath.engine.es import ElasticsearchEngine
    >>> from fhirpath.engine import dialect_factory
    >>> from fhirpath.enums import FHIR_VERSION

    >>> host, port = "127.0.0.1", 9200
    >>> conn_str = "es://@{0}:{1}/".format(host, port)
    >>> connection = create_connection(conn_str, "elasticsearch.Elasticsearch")
    >>> connection.raw_connection.ping()
    True
    >>> engine = ElasticsearchEngine(FHIR_VERSION.R4, lambda x: connection, dialect_factory)


Basic Search::

    >>> from fhirpath.search import Search
    >>> from fhirpath.search import SearchContext

    >>> search_context = SearchContext(engine, "Organization")
    >>> params = (
    ....    ("active", "true"),
    ....    ("_lastUpdated", "2010-05-28T05:35:56+00:00"),
    ....    ("_profile", "http://hl7.org/fhir/Organization"),
    ....    ("identifier", "urn:oid:2.16.528.1|91654"),
    ....    ("type", "http://hl7.org/fhir/organization-type|prov"),
    ....    ("address-postalcode", "9100 AA"),
    ....    ("address", "Den Burg"),
    .... )
    >>> fhir_search = Search(search_context, params=params)
    >>> bundle = fhir_search()
    >>> len(bundle.entry) == 0
    True

Basic Query::

    >>> from fhirpath.enums import SortOrderType
    >>> from fhirpath.query import Q_
    >>> from fhirpath.fql import T_
    >>> from fhirpath.fql import V_
    >>> from fhirpath.fql import exists_
    >>> query_builder = Q_(resource="Organization", engine=engine)
    >>>  query_builder = (
    ....    query_builder.where(T_("Organization.active") == V_("true"))
    ....    .where(T_("Organization.meta.lastUpdated", "2010-05-28T05:35:56+00:00"))
    ....    .sort(sort_("Organization.meta.lastUpdated", SortOrderType.DESC))
    .... )
    >>> query_result = query_builder(async_result=False)
    >>> for resource in query_result:
    ....    assert resource.__class__.__name__ == "OrganizationModel"
    >>> # test fetch all
    >>> result = query_result.fetchall()
    >>> result.__class__.__name__ == "EngineResult"
    True

    >>> query_builder = Q_(resource="ChargeItem", engine=engine)
    >>> query_builder = query_builder.where(exists_("ChargeItem.enteredDate"))
    >>> result = query_builder(async_result=False).single()
    >>> result is not None
    True
    >>> isinstance(result, builder._from[0][1])
    True

    >>> query_builder = Q_(resource="ChargeItem", engine=engine)
    >>> query_builder = query_builder.where(exists_("ChargeItem.enteredDate"))
    >>> result = query_builder(async_result=False).first()
    >>> result is not None
    True
    >>> isinstance(result, builder._from[0][1])
    True


Available Provider (known)
--------------------------

Currently very few numbers of providers available, however more will coming soon.

`fhirpath-guillotina`_
~~~~~~~~~~~~~~~~~~~~~~

A `guillotina`_ framework powered provider, battery included, ready to go! `Please follow associated documentation. <https://fhirpath-guillotina.readthedocs.io/en/latest/>`_

1. **Engine**: Elasticsearch

2. **PyPi**: https://pypi.org/project/fhirpath-guillotina/

3. **Source**: https://github.com/nazrulworld/fhirpath_guillotina


`collective.fhirpath`_
~~~~~~~~~~~~~~~~~~~~~~

A `Plone`_ powered provider, like `fhirpath-guillotina`_ every thing is included. ready to go, although has a dependency
on `plone.app.fhirfield`_.

1. **Engine**: Elasticsearch

2. **PyPi**: https://pypi.org/project/collective.fhirpath/

3. **Source**: https://github.com/nazrulworld/collective.fhirpath


unlisted
~~~~~~~~
Why are you waiting for? You are welcome to list your provider here!
Developing provider should not be so hard, as ``fhirpath`` is giving you convenient APIs.


Elasticsearch Custom Analyzer
-----------------------------
To get some special search features for reference type field, you will need to setup custom analyzer for your elasticsearch index.

Example Custom Analyzer::

    settings = {
        "analysis": {
            "normalizer": {
                "fhir_token_normalizer": {"filter": ["lowercase", "asciifolding"]}
            },
            "analyzer": {
                "fhir_reference_analyzer": {
                    "tokenizer": "keyword",
                    "filter": ["fhir_reference_filter"],
                },
            },
            "filter": {
                "fhir_reference_filter": {
                    "type": "pattern_capture",
                    "preserve_original": True,
                    "patterns": [r"(?:\w+\/)?(https?\:\/\/.*|[a-zA-Z0-9_-]+)"],
                },
            },
            "char_filter": {},
            "tokenizer": {},
        }


Example Mapping (Reference Field)::

    "properties": {
      "reference": {
        "type": "text",
        "index": true,
        "store": false,
        "analyzer": "fhir_reference_analyzer"
    }


ToDo
----

1. `fhirbase`_ engine aka provider implementation.

2. Implement https://github.com/ijl/orjson
3. https://developers.redhat.com/blog/2017/11/16/speed-python-using-rust/

Credits
-------

This package skeleton was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
.. _`FHIRPath`: https://hl7.org/fhirpath/
.. _`FHIR`: http://hl7.org/fhir/
.. _`ORM`: https://en.wikipedia.org/wiki/Object-relational_mapping
.. _`Plone`: https://plone.org
.. _`guillotina`: https://guillotina.readthedocs.io/en/latest/
.. _`elasticsearch`: https://www.elastic.co/products/elasticsearch
.. _`GraphQL`: https://graphql.org/
.. _`PostgreSQL`: https://www.postgresql.org/
.. _`fhirpath-guillotina`: https://pypi.org/project/fhirpath-guillotina/
.. _`collective.fhirpath`: https://pypi.org/project/collective.fhirpath/
.. _`plone.app.fhirfield`: https://pypi.org/project/plone.app.fhirfield/
.. _`fhirbase`: https://github.com/fhirbase/fhirbase


© Copyright HL7® logo, FHIR® logo and the flaming fire are registered trademarks
owned by `Health Level Seven International <https://www.hl7.org/legal/trademarks.cfm?ref=https://pypi.org/project/fhir-resources/>`_

**"FHIR® is the registered trademark of HL7 and is used with the permission of HL7.
Use of the FHIR trademark does not constitute endorsement of this product by HL7"**
