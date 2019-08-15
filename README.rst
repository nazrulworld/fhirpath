========
fhirpath
========


.. image:: https://img.shields.io/pypi/v/fhirpath.svg
        :target: https://pypi.python.org/pypi/fhirpath

.. image:: https://img.shields.io/travis/nazrulworld/fhirpath.svg
        :target: https://travis-ci.org/nazrulworld/fhirpath

.. image:: https://readthedocs.org/projects/fhirpath/badge/?version=latest
        :target: https://fhirpath.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status


.. image:: https://pyup.io/repos/github/nazrulworld/fhirpath/shield.svg
     :target: https://pyup.io/repos/github/nazrulworld/fhirpath/
     :alt: Updates

.. image:: https://fire.ly/wp-content/themes/fhir/images/fhir.svg
        :target: https://www.hl7.org/fhir/fhirpath.html
        :alt: HL7® FHIR®

fhirpath_ implementation in Python. This library is built in ORM_ like approach.

* Supports multiple provider´s engine. Now Plone_ & guillotina_ are supported and more coming soon.
* Supports multiple dialects, for example elasticsearch_, GraphQL_,PostgreSQL_. Although now elasticsearch_ has been supported.
* Provide full support of `FHIR Search <https://www.hl7.org/fhir/search.html>`_ with easy to use API.


Quickstart (guillotina_)
------------------------

This quickstarter guide is based on guillotina_ and elasticsearch_ with extra ``guillotina_elasticsearch`` dependency.
If don´t know about guillotina_, have a `look at their nice document <https://guillotina.readthedocs.io/en/latest/>`_.
Add ``fhirpath`` and `guillotina_elasticsearch <https://pypi.org/project/guillotina-elasticsearch/>`_ in your project dependencies.
Install ``fhirpath.providers.guillotina_app`` from `your app configuration file <https://guillotina.readthedocs.io/en/latest/training/configuration.html#installing-applications>`_.


**we assume you configure elasticsearch_ service properly and have FHIR_ content types and latstly of course you know about FHIR_**

Example: Add Contents::

    class IOrganization(IFhirContent, IContentIndex):
        index_field(
            "organization_resource",
            type="object",
            field_mapping=fhir_resource_mapping("Organization"),
            fhirpath_enabled=True,
            resource_type="Organization",
            fhir_version=FHIR_VERSION.DEFAULT,
        )
        index_field("org_type", type="keyword")
        org_type = TextLine(title="Organization Type", required=False)
        organization_resource = FhirField(
            title="Organization Resource", resource_type="Organization", fhir_version="R4"
        )


    @configure.contenttype(type_name="Organization", schema=IOrganization)
    class Organization(Folder):
        """ """

        index(schemas=[IOrganization], settings={})
        resource_type = "Organization"


Example Search::

    >>> from guillotina.component import query_utility
    >>> from fhirpath.interfaces import ISearchContextFactory
    >>> from fhirpath.providers.guillotina_app.interfaces import IFhirSearch
    >>> search_context = query_utility(ISearchContextFactory).get(
    ...    resource_type="Organization"
    ... )
    >>> search_tool = query_utility(IFhirSearch)
    >>> params = (
    ...     ("active", "true"),
    ...     ("_lastUpdated", "2010-05-28T05:35:56+00:00"),
    ...     ("_profile", "http://hl7.org/fhir/Organization"),
    ...     ("identifier", "urn:oid:2.16.528.1|91654"),
    ...     ("type", "http://hl7.org/fhir/organization-type|prov"),
    ...     ("address-postalcode", "9100 AA")
    ... )
    >>> fhir_bundle = await search_tool(params, context=search_context)
    >>> fhir_bundle.total == len(fhir_bundle.entry)

Example FhirPath Query::

    >>> from fhirpath.providers.guillotina_app.interfaces import IElasticsearchEngineFactory
    >>> from guillotina.component import query_utility
    >>> from fhirpath.enums import SortOrderType
    >>> from fhirpath.fql import Q_
    >>> from fhirpath.fql import T_
    >>> from fhirpath.fql import V_
    >>> from fhirpath.fql import sort_
    >>> engine = query_utility(IElasticsearchEngineFactory).get()
    >>> query_builder = Q_(resource="Organization", engine=engine)
    >>> query_builder = (
    ...        query_builder.where(T_("Organization.active") == V_("true"))
    ...        .where(T_("Organization.meta.lastUpdated", "2010-05-28T05:35:56+00:00"))
    ...        .sort(sort_("Organization.meta.lastUpdated", SortOrderType.DESC))
    ...        .limit(20)
    ...    )
    >>> query_result = query_builder(async_result=True)
    >>> result = query_result.fetchall()
    >>> result.header.total == 100
    True
    >>> len(result.body) == 20
    True
    >>> async for resource in query_result:
    ...     assert resource.resource_type == "Organization"


Credits
-------

This package skeleton was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
.. _`fhirpath`: http://hl7.org/fhirpath/
.. _`FHIR`: http://hl7.org/fhir/
.. _`ORM`: https://en.wikipedia.org/wiki/Object-relational_mapping
.. _`Plone`: https://plone.org
.. _`guillotina`: https://guillotina.readthedocs.io/en/latest/
.. _`elasticsearch`: https://www.elastic.co/products/elasticsearch
.. _`GraphQL`: https://graphql.org/
.. _`PostgreSQL`: https://www.postgresql.org/


© Copyright HL7® logo, FHIR® logo and the flaming fire are registered trademarks
owned by `Health Level Seven International <https://www.hl7.org/legal/trademarks.cfm?ref=https://pypi.org/project/fhir-resources/>`_
