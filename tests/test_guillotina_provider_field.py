#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `guillotina_fhirfield` package."""

import os
import pathlib
import pickle

import pytest
import ujson as json
from guillotina.component import get_multi_adapter
from guillotina.component import get_utility
from guillotina.component import query_adapter
from guillotina.interfaces import IFactorySerializeToJson
from guillotina.interfaces import IJSONToValue
from guillotina.interfaces import IResourceFactory
from guillotina.interfaces import ISchemaFieldSerializeToJson
from guillotina.interfaces import ISchemaSerializeToJson
from guillotina.interfaces import IValueToJson
from guillotina.schema.exceptions import ConstraintNotSatisfied
from guillotina.schema.exceptions import WrongContainedType
from guillotina.schema.exceptions import WrongType
from zope.interface import Invalid
from zope.interface import implementer

from fhirpath.engine.providers.guillotina_provider.field import FhirField
from fhirpath.engine.providers.guillotina_provider.field import FhirFieldValue
from fhirpath.engine.providers.guillotina_provider.field import (
    fhir_field_from_resource_type,
)
from fhirpath.engine.providers.guillotina_provider.field import fhir_field_from_schema
from fhirpath.engine.providers.guillotina_provider.helpers import parse_json_str
from fhirpath.engine.providers.guillotina_provider.interfaces import IFhirField
from fhirpath.engine.providers.guillotina_provider.interfaces import IFhirFieldValue
from fhirpath.engine.providers.guillotina_provider.interfaces import IFhirResource
from fhirpath.utils import import_string
from fhirpath.utils import lookup_fhir_class_path

from .fixtures import IOrganization


FHIR_EXAMPLE_RESOURCES = (
    pathlib.Path(os.path.abspath(__file__)).parent / "static" / "FHIR"
)


def test_field_init_validate(dummy_guillotina):  # noqa: C901,E999
    """ """
    # Test with minimal params
    try:
        FhirField(title="Organization resource")
    except Invalid as exc:
        raise AssertionError(
            "Code should not come here, as everything should goes fine.\n{0!s}".format(
                exc
            )
        )
    # Test with fhir field specific params
    try:
        FhirField(
            title="Organization resource",
            resource_class="tests.fixtures.MyOrganizationResource",
            resource_interface=(
                "fhirpath.engine.providers."
                "guillotina_provider.interfaces.IFhirResource"),
        )
    except Invalid as exc:
        raise AssertionError(
            "Code should not come here, as everything should goes fine.\n{0!s}".format(
                exc
            )
        )

    try:
        FhirField(title="Organization resource", resource_type="Organization")
    except Invalid as exc:
        raise AssertionError(
            "Code should not come here, as everything should goes fine.\n{0!s}".format(
                exc
            )
        )

    # resource_type and model are not allowed combinely
    try:
        FhirField(
            title="Organization resource",
            resource_type="Organization",
            resource_class="fhir.resources.organization.Organization",
        )
        raise AssertionError("Code should not come here! as should be invalid error")
    except Invalid:
        pass

    # test with invalid python style dotted path (fake module)
    try:
        FhirField(
            title="Organization resource",
            resource_class="fake.fake.models.organization.Organization",
        )
        raise AssertionError("Code should not come here! as should be invalid error")
    except Invalid:
        pass

    # test with invalid fhir model
    try:
        FhirField(
            title="Organization resource", resource_class="guillotina.content.Resource"
        )
        raise AssertionError("Code should not come here! as should be invalid error")
    except Invalid as exc:
        assert "has not been derrived from FHIRAbstractBase class" in str(exc)

    # test with invalid ResourceType
    try:
        FhirField(title="Organization resource", resource_type="FakeResource")
        raise AssertionError("Code should not come here! as should be invalid error")
    except Invalid as exc:
        assert "FakeResource is not valid fhir resource type" in str(exc)

    # Wrong base interface class


# async def test_field_init_validation_with_noninterface(dummy_guillotina):

#     """ """
#     # Wrong interface class
#     try:
#         FhirField(
#             title="Organization resource",
#             resource_interface="guillotina_fhirfield.tests.helpers.NoneInterfaceClass",
#         )
#         raise AssertionError(
#             "Code should not come here! as wrong interface class is provided"
#         )
#     except WrongType as exc:
#         assert "An interface is required" in str(exc)


# async def test_field_init_validation_with_wrong_dotted_path(dummy_guillotina):
#     """ """
#     # Wrong module path
#     try:
#         FhirField(
#             title="Organization resource",
#             resource_interface="fake.tests.NoneInterfaceClass",
#         )
#         raise AssertionError(
#             "Code should not come here! as wrong interface class is provided"
#         )
#     except Invalid as exc:
#         assert "Invalid FHIR Resource Interface" in str(exc)


# async def test_field_pre_value_validate(dummy_guillotina):
#     """ """
#     with open(str(FHIR_FIXTURE_PATH / "Organization.json"), "r") as f:
#         json_str = f.read()

#     fhir_field = FhirField(title="Organization resource")

#     try:
#         fhir_field._pre_value_validate(json_str)
#     except Invalid as e:
#         raise AssertionError("Code should not come here!\n{0!s}".format(e))

#     fhir_dict = json.loads(json_str)
#     resource_type = fhir_dict.pop("resourceType")

#     try:
#         fhir_field._pre_value_validate(fhir_dict)
#         raise AssertionError(
#             "Code should not come here! As `resourceType` is not exists."
#         )
#     except Invalid:
#         pass

#     fhir_dict.pop("id")
#     fhir_dict["resourceType"] = resource_type
#     try:
#         fhir_field._pre_value_validate(fhir_dict)
#         raise AssertionError("Code should not come here! As `id` is not exists.")
#     except Invalid:
#         pass

#     fhir_dict.pop("resourceType")
#     try:
#         fhir_field._pre_value_validate(fhir_dict)
#         raise AssertionError(
#             "Code should not come here! As both `id` and `resourceType` are not exists."
#         )
#     except Invalid:
#         pass


# async def test_field_validate(dummy_guillotina):
#     """ """
#     with open(str(FHIR_FIXTURE_PATH / "Organization.json"), "r") as f:
#         json_dict = json.load(f)

#     organization = resource_type_to_resource_cls("Organization")(json_dict)
#     fhir_resource_value = FhirFieldValue(obj=organization)

#     fhir_field = FhirField(title="Organization resource")

#     try:
#         fhir_field._validate(fhir_resource_value)
#     except Invalid as exc:
#         raise AssertionError("Code should not come here!\n{0!s}".format(exc))

#     # Test wrong type value!
#     try:
#         fhir_field._validate(dict(hello="wrong"))
#         raise AssertionError("Code should not come here! wrong data type is provide")
#     except WrongType as exc:
#         assert "guillotina_fhirfield.field.FhirFieldValue" in str(exc)

#     type_, address_ = fhir_resource_value.type, fhir_resource_value.address
#     fhir_resource_value.type = 390
#     fhir_resource_value.address = "i am wrong type"

#     try:
#         fhir_field._validate(fhir_resource_value)
#         raise AssertionError(
#             "Code should not come here! wrong element data type is provided"
#         )
#     except Invalid as exc:
#         assert "invalid element inside fhir model object" in str(exc)

#     # Restore
#     fhir_resource_value.type = type_
#     fhir_resource_value.address = address_
#     # Test model constraint
#     fhir_field = FhirField(
#         title="Organization resource", resource_class="fhir.resources.task.Task"
#     )

#     try:
#         fhir_field._validate(fhir_resource_value)
#         raise AssertionError("Code should not come here! model mismatched!")
#     except WrongContainedType as exc:
#         assert "Wrong fhir resource value" in str(exc)

#     # Test resource type constraint!
#     fhir_field = FhirField(title="Organization resource", resource_type="Task")

#     try:
#         fhir_field._validate(fhir_resource_value)
#         raise AssertionError("Code should not come here! model mismatched!")
#     except ConstraintNotSatisfied as exc:
#         assert "Resource type must be `Task`" in str(exc)

#     # Wrong interface attributes
#     fhir_field = FhirField(
#         title="Organization resource",
#         resource_interface="guillotina_fhirfield.tests.helpers.IWrongInterface",
#     )

#     try:
#         fhir_field._validate(fhir_resource_value)
#         raise AssertionError(
#             "Code should not come here! interface and object mismatched!"
#         )
#     except Invalid as exc:
#         assert "An object does not implement" in str(exc)


# async def test_field_from_dict(dummy_guillotina):
#     """ """
#     with open(str(FHIR_FIXTURE_PATH / "Organization.json"), "r") as f:
#         json_dict = json.load(f)

#     fhir_field = FhirField(
#         title="Organization resource",
#         resource_class="fhir.resources.organization.Organization",
#     )

#     try:
#         fhir_resource_value = fhir_field.from_dict(json_dict)
#     except Invalid as exc:
#         raise AssertionError(
#             "Code should not come here! as should return valid FhirResourceValue.\n{0!s}".format(
#                 exc
#             )
#         )

#     assert fhir_resource_value.resource_type == json_dict["resourceType"]

#     fhir_field = FhirField(title="Organization resource", resource_type="Organization")

#     fhir_resource_value = fhir_field.from_dict(json_dict)
#     try:
#         fhir_resource_value.as_json()
#     except Exception:
#         raise AssertionError(
#             "Code should not come here! as should be valid fhir resource"
#         )

#     # Test auto discovery resource type
#     fhir_field = FhirField(title="Organization resource")
#     fhir_resource_value = fhir_field.from_dict(json_dict)
#     assert fhir_resource_value.resource_type == json_dict["resourceType"]

#     # Test with invalid data type
#     try:
#         invalid_data = ("hello", "tree", "go")
#         fhir_field.from_dict(invalid_data)
#     except WrongType as exc:
#         assert "Only dict type data is allowed" in str(exc)

#     # Test with invalid fhir data
#     try:
#         invalid_data = dict(hello="fake", foo="bar")
#         fhir_field.from_dict(invalid_data)

#         raise AssertionError("Code should not come here, because of invalid data")
#     except Invalid as exc:
#         assert "Invalid FHIR resource" in str(exc)

#     # Test constraint
#     fhir_field = FhirField(
#         title="Organization resource", resource_class="fhir.resources.task.Task"
#     )

#     try:
#         fhir_field.from_dict(json_dict)
#         raise AssertionError(
#             "Code should not come here as required fhir model is mismatched with provided resourcetype"
#         )
#     except ConstraintNotSatisfied as exc:
#         assert "Fhir Resource mismatched" in str(exc)


# async def test_field_from_unicode(dummy_guillotina):
#     """ """
#     with open(str(FHIR_FIXTURE_PATH / "Organization.json"), "r") as f:
#         json_str = f.read()

#     fhir_field = FhirField(
#         title="Organization resource",
#         resource_class="fhir.resources.organization.Organization",
#     )

#     try:
#         fhir_field.from_unicode(json_str)
#     except Invalid as exc:
#         raise AssertionError(
#             "Code should not come here! as should return valid FhirResourceValue.\n{0!s}".format(
#                 exc
#             )
#         )

#     # Test with invalid json string
#     try:
#         invalid_data = "{hekk: invalg, 2:3}"
#         fhir_field.from_unicode(invalid_data)
#         raise AssertionError(
#             "Code should not come here! invalid json string is provided"
#         )
#     except Invalid as exc:
#         assert "Invalid JSON String" in str(exc)


# async def test_field_from_unicode_with_empty_str(dummy_guillotina):
#     """ """
#     fhir_field = FhirField(
#         title="Organization resource",
#         resource_class="fhir.resources.organization.Organization",
#         required=False,
#     )

#     value = fhir_field.from_unicode("")
#     assert value is None


# async def test_field_default_value(dummy_guillotina):
#     """ """
#     with open(str(FHIR_FIXTURE_PATH / "Organization.json"), "r") as f:
#         json_dict = json.load(f)

#     fhir_field = FhirField(
#         title="Organization resource",
#         resource_class="fhir.resources.organization.Organization",
#         default=json_dict,
#     )
#     assert json_dict == fhir_field.default.as_json()

#     fhir_field2 = FhirField(
#         title="Organization resource",
#         resource_class="fhir.resources.organization.Organization",
#         default=json.dumps(json_dict),
#     )

#     assert fhir_field2.default.as_json() == fhir_field.default.as_json()

#     fhir_field3 = FhirField(
#         title="Organization resource",
#         resource_class="fhir.resources.organization.Organization",
#         default=None,
#     )
#     assert fhir_field3.default is None


# async def test_field_with_wrong_default_value(dummy_guillotina):
#     """ """
#     try:
#         FhirField(
#             title="Organization resource",
#             resource_class="fhir.resources.organization.Organization",
#             default=False,
#         )
#     except Invalid as exc:
#         assert "Only dict or string or None is accepted" in str(exc)
#     try:
#         FhirField(
#             title="Organization resource",
#             resource_class="fhir.resources.organization.Organization",
#             default={"id": "I am wrong FHIR"},
#         )
#     except Invalid as exc:
#         assert "Invalid FHIR resource json is provided!" in str(exc)


# async def test_field_resource_type_constraint(dummy_guillotina):
#     """Regarding to issue: #3 """
#     fhir_field = FhirField(title="Organization resource", resource_type="Organization")
#     with open(str(FHIR_FIXTURE_PATH / "Patient.json"), "r") as f:
#         json_dict = json.load(f)

#     try:
#         fhir_field.from_dict(json_dict)
#     except Invalid as e:
#         assert e.__class__.__name__ == "ConstraintNotSatisfied"
#         assert "Fhir Resource mismatched" in str(e)


# async def test_fhir_field_value(dummy_guillotina):
#     """ """
#     with open(str(FHIR_FIXTURE_PATH / "Organization.json"), "r") as f:
#         fhir_json = json.load(f)

#     model = resource_type_to_resource_cls(fhir_json["resourceType"])
#     fhir_resource = model(fhir_json)
#     fhir_resource_value = FhirFieldValue(obj=fhir_resource)

#     # __bool__ should be True
#     assert bool(fhir_resource_value) is True
#     assert IFhirResource.providedBy(fhir_resource_value.foreground_origin()) is True
#     assert isinstance(fhir_resource_value.stringify(), str) is True

#     # Test Patch
#     patch_data = {"hello": 123}
#     try:
#         fhir_resource_value.patch(patch_data)
#         raise AssertionError(
#             "Code should not come here! because wrong type data is provided for patch!"
#         )
#     except WrongType:
#         pass
#     patch_data = [
#         {"path": "/text/fake path", "value": "patched!", "Invalid Option": "replace"}
#     ]
#     # Test getting original error from json patcher
#     try:
#         fhir_resource_value.patch(patch_data)
#         raise AssertionError(
#             "Code should not come here! because wrong patch data is"
#             " provided for patch and invalid format as well!"
#         )
#     except Invalid as exc:
#         assert "does not contain 'op' member" in str(exc)

#     patch_data = [{"path": "/text/status", "value": "patched!", "op": "replace"}]
#     fhir_resource_value.patch(patch_data)

#     assert "patched!" == fhir_resource_value.text.status

#     # Make sure string is transformable to fhir resource
#     json_str = fhir_resource_value.stringify()
#     json_dict = parse_json_str(json_str)

#     try:
#         model(json_dict).as_json()
#     except Exception:
#         raise AssertionError("Code should not come here!")

#     # Test self representation
#     assert fhir_resource_value.__class__.__module__ in repr(fhir_resource_value)

#     empty_resource = FhirFieldValue()
#     # __bool__ should be False
#     assert bool(empty_resource) is False

#     assert empty_resource.foreground_origin() is None

#     assert (fhir_resource_value == empty_resource) is False
#     assert (empty_resource == fhir_resource_value) is False
#     assert (empty_resource != fhir_resource_value) is True

#     # Test Patch with empty value
#     try:
#         empty_resource.patch(patch_data)
#         raise AssertionError(
#             "Code should not come here! because empty resource cannot be patched!"
#         )
#     except Invalid:
#         pass

#     # Let's try to modify
#     fhir_resource_value.identifier[0].use = "no-official"

#     # test if it impact
#     assert fhir_resource_value.as_json()["identifier"][0]["use"] == "no-official"

#     # Let's try to set value on empty value
#     try:
#         empty_resource.id = "my value"
#         raise AssertionError("Code should not come here! because no fhir resource!")
#     except AttributeError:
#         pass

#     assert "NoneType" in repr(empty_resource)
#     assert "" == str(empty_resource)

#     # Validation Test:: more explict???
#     try:
#         FhirFieldValue(obj=dict(hello="Ketty"))
#         raise AssertionError(
#             "Code should not come here, because should raise validation error!"
#         )
#     except WrongType:
#         pass

#     @implementer(IFhirResource)
#     class TestBrokenInterfaceObject(object):
#         def __init__(self):
#             pass

#     broken_obj = TestBrokenInterfaceObject()
#     try:
#         fhir_resource_value._validate_object(broken_obj)
#         raise AssertionError("Code should not come here! because of validation error")
#     except Invalid as exc:
#         assert " The resource_type attribute was not provided" in str(exc)


# async def test_fhir_field_value_pickling(dummy_guillotina):
#     """ """
#     with open(str(FHIR_FIXTURE_PATH / "Organization.json"), "r") as f:
#         fhir_json = json.load(f)

#     model = resource_type_to_resource_cls(fhir_json["resourceType"])
#     fhir_resource = model(fhir_json)
#     fhir_resource_value = FhirFieldValue(obj=fhir_resource)

#     serialized = pickle.dumps(fhir_resource_value)
#     deserialized = pickle.loads(serialized)

#     assert len(deserialized.stringify()) == len(fhir_resource_value.stringify())


# async def test_fhir_field_value_serializer(dummy_request):
#     """ """
#     with open(str(FHIR_FIXTURE_PATH / "Organization.json"), "r") as f:
#         fhir_json = json.load(f)

#     model = resource_type_to_resource_cls(fhir_json["resourceType"])
#     fhir_resource = model(fhir_json)
#     value = FhirFieldValue(obj=fhir_resource)

#     serialized = query_adapter(value, IValueToJson)
#     assert serialized == value.as_json()

#     serialized = query_adapter(FhirFieldValue(), IValueToJson)

#     assert serialized is None


# async def test_fhir_field_deserializer(dummy_request):
#     """ """
#     with open(str(FHIR_FIXTURE_PATH / "Organization.json"), "r") as f:
#         fhir_json = json.load(f)

#     fhir_field = FhirField(
#         title="Organization resource",
#         resource_class="fhir.resources.organization.Organization",
#         required=False,
#     )

#     deserialized = query_adapter(fhir_field, IJSONToValue, args=[fhir_json, None])
#     assert IFhirFieldValue.providedBy(deserialized) is True
#     assert deserialized.as_json() == fhir_json

#     deserialized = query_adapter(
#         fhir_field, IJSONToValue, args=[json.dumps(fhir_json), None]
#     )
#     assert IFhirFieldValue.providedBy(deserialized) is True

#     deserialized = query_adapter(fhir_field, IJSONToValue, args=[None, None])
#     assert deserialized is None


# async def test_fhir_field_schema_serializer(dummy_request):
#     """ """
#     fhir_field = FhirField(
#         title="Organization resource",
#         resource_class="fhir.resources.organization.Organization",
#     )

#     serializer = get_multi_adapter(
#         (fhir_field, IOrganization, dummy_request),
#         ISchemaFieldSerializeToJson)

#     schema_json = await serializer()
#     assert schema_json['type'] == 'FhirField'
#     assert schema_json['resource_class'] == 'fhir.resources.organization.Organization'


# async def test_schema_serializer_with_fhir_field(dummy_request):
#     """ """
#     serializer = get_multi_adapter(
#         (IOrganization, dummy_request),
#         ISchemaSerializeToJson)

#     serialized_schema = await serializer()
#     assert 'organization_resource' in serialized_schema['properties']
#     assert 'organization_resource' in serialized_schema['required']


# async def test_factory_serializer_with_fhir_field(dummy_request):
#     """ """
#     factory = get_utility(IResourceFactory, name='Organization')

#     serializer = get_multi_adapter(
#         (factory, dummy_request),
#         IFactorySerializeToJson)

#     serialized_factory = await serializer()
#     assert 'organization_resource' in serialized_factory['properties']
#     assert 'organization_resource' in serialized_factory['required']


# async def test_fhir_field_from_schema(dummy_guillotina):
#     """ """

#     expected_fhir_field = fhir_field_from_schema(IOrganization, 'Organization')

#     assert expected_fhir_field is not None

#     assert IFhirField.providedBy(expected_fhir_field)
#     # test with mismatched resource type
#     assert fhir_field_from_schema(IOrganization, 'Patient') is None


# async def test_fhir_field_from_resource_type(dummy_guillotina):
#     """ """

#     fields = fhir_field_from_resource_type('Organization')
#     """{
#             'organization_resource': {
#                 'field': <guillotina_fhirfield.field.FhirField object at 0x7f214c54dfd0>,
#                 'types': ['Organization']
#             }
#         }"""
#     assert len(fields) == 1
#     assert 'organization_resource' in fields

#     # test non existing
#     assert fhir_field_from_resource_type('Patient') is None

#     with pytest.raises(Invalid):
#         fhir_field_from_resource_type('FakeResource')


# async def test_query_builder(container_requester):
#     """Check list of content types."""
#
#     async with container_requester as requester:
#         data = (
#             ('part-of:missing', 'true'),
#             ('identifier', 'CPR|240365-0002'),
#             ('identifier', 'CPR|240365-0001'),
#             ('price-override', 'gt39.99|urn:iso:std:iso:4217|EUR')
#         )
#         response, status = await requester(
#             'GET',
#             '/db/guillotina/@fhir/Patient',
#             params=data
#         )
#         assert status == 200
