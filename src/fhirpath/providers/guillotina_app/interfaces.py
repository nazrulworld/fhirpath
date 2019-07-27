# -*- coding: utf-8 -*-
"""Module where all interfaces, events and exceptions live."""
from guillotina.interfaces import IResource
from guillotina.schema import ASCIILine
from guillotina.schema import DottedName
from guillotina.schema import TextLine
from guillotina.schema.interfaces import IObject
from zope.interface import Attribute
from zope.interface import Interface

from fhirpath.interfaces import IEngineFactory
from fhirpath.interfaces import IModel


class IFhirContent(IResource):
    """ """

    resource_type = TextLine(readonly=True)


class IFhirResource(IModel):
    """ """

    resource_type = Attribute("resource_type", "Resource Type")
    id = Attribute("id", "Logical id of this artifact.")
    implicitRules = Attribute(
        "implicitRules", "A set of rules under which this content was created."
    )
    language = Attribute("language", "Language of the resource content.")
    meta = Attribute("meta", "Metadata about the resource")

    def as_json():
        """ """


class IFhirField(IObject):
    """ """

    resource_type = TextLine(title="FHIR Resource Type", required=False)
    resource_class = DottedName(
        title="FHIR Resource custom class that is based from fhir.resources",
        required=False,
    )
    resource_interface = DottedName(title="FHIR Resource Interface", required=False)
    fhir_version = ASCIILine(title="FHIR Release Version", required=True)

    def from_dict(dict_value):
        """ """


class IFhirFieldValue(Interface):
    """ """

    _resource_obj = Attribute(
        "_resource_obj", "_resource_obj to hold Fhir resource model object."
    )

    def stringify(prettify=False):
        """Transformation to JSON string representation"""

    def patch(patch_data):
        """FHIR Patch implementation: https://www.hl7.org/fhir/fhirpatch.html"""

    def foreground_origin():
        """Return the original object of FHIR model that is proxied!"""


class IElasticsearchEngineFactory(IEngineFactory):
    """ """


class IFhirSearch(Interface):
    """ """
