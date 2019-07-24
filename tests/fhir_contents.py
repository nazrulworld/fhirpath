from guillotina import configure
from guillotina.api.service import Service
from guillotina.component import get_utility
from guillotina.content import Folder
from guillotina.directives import index_field
from guillotina.interfaces import ICatalogUtility
from guillotina.interfaces import IContainer
from guillotina_elasticsearch.directives import index
from guillotina_elasticsearch.interfaces import IContentIndex

from guillotina_fhirfield.field import FhirField
from guillotina_fhirfield.helpers import fhir_resource_mapping
from guillotina_fhirfield.interfaces import IFhirContent


class IOrganization(IFhirContent, IContentIndex):

    index_field(
        'organization_resource',
        type='object',
        field_mapping=fhir_resource_mapping('Organization'),
        fhir_field_indexer=True,
        resource_type='Organization'

    )

    organization_resource = FhirField(
        title='Organization Resource',
        resource_type='Organization'
    )


@configure.contenttype(
    type_name="Organization",
    schema=IOrganization)
class Organization(Folder):
    """ """
    index(
        schemas=[IOrganization],
        settings={

        }
    )
    resource_type = 'Organization'


@configure.service(
    context=IContainer, method='GET',
    permission='guillotina.AccessContent', name='@fhir/{resource_type}',
    summary='FHIR search result',
    responses={
        "200": {
            "description": "Result results on FHIR Bundle",
            "schema": {
                "properties": {}
            }
        }
    })
class FhirServiceSearch(Service):

    async def prepare(self):
        pass

    async def __call__(self):
        catalog = get_utility(ICatalogUtility)
        result = await catalog.stats(self.context)
        #import pytest;pytest.set_trace()
        """ self.request.query
<MultiDictProxy('part-of:missing': 'true', 'identifier': 'CPR|240365-0002', 'identifier': 'CPR|240365-0001', 'price-override': 'gt39.99|urn:iso:std:iso:4217|EUR')>
"""
