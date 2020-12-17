============
Introduction
============

.. image:: https://img.shields.io/travis/nazrulworld/fhirpath.svg
        :target: https://travis-ci.org/nazrulworld/fhirpath

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

FHIRPath_ Normative Release (v2.0.0) implementation in Python, along side it
provides support for `FHIR Search <https://www.hl7.org/fhir/search.html>`_ API and
Query (we called it ``fql(FHIR Query Language)``)
API to fetch FHIR resources from any data-source(database).
This library is built in ORM_ like approach. Our goal is to make 100% (as much as possible)
FHIRPath_ Normative Release (v2.0.0) specification compliance product.

* Supports FHIR® ``STU3`` and ``R4``.
* Supports multiple provider´s engine. Now Plone_ & guillotina_ framework powered providers `fhirpath-guillotina`_ and `collective.fhirpath`_ respectively are supported and more coming soon.
* Supports multiple dialects, for example elasticsearch_, GraphQL_, PostgreSQL_. Although now elasticsearch_ has been supported.
* Provide full support of `FHIR Search <https://www.hl7.org/fhir/search.html>`_ with easy to use API.


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

2. All methods/functions are defined in `FHIRPath`_ specification, would be completed.

3. Implement https://github.com/ijl/orjson
4. https://developers.redhat.com/blog/2017/11/16/speed-python-using-rust/

Credits
-------

This package skeleton was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
.. _`FHIRPath`: http://hl7.org/fhirpath/N1/
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
