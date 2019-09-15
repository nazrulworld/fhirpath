=====
Usage
=====

This library is kind of abstract type, where all specifications from fhirpath_ are implemented rather than completed solution (ready to go).
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

.. _`fhirpath`: http://hl7.org/fhirpath/
