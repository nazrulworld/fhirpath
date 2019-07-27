# -*- coding: utf-8 -*-
import inspect
from collections import OrderedDict
from typing import NewType
from typing import Union

import jsonpatch
import ujson
from fhir.resources.fhirabstractbase import FHIRValidationError
from guillotina import configure
from guillotina import directives
from guillotina.component import get_utilities_for
from guillotina.interfaces import IResourceFactory
from guillotina.interfaces import ISchemaFieldSerializeToJson
from guillotina.json.serialize_schema_field import DefaultSchemaFieldSerializer
from guillotina.schema import Object
from guillotina.schema import get_fields
from guillotina.schema import get_fields_in_order
from guillotina.schema.exceptions import ConstraintNotSatisfied
from guillotina.schema.exceptions import WrongContainedType
from guillotina.schema.exceptions import WrongType
from guillotina.schema.interfaces import IFromUnicode
from zope.interface import Interface
from zope.interface import Invalid
from zope.interface import implementer
from zope.interface.exceptions import BrokenImplementation
from zope.interface.exceptions import BrokenMethodImplementation
from zope.interface.exceptions import DoesNotImplement
from zope.interface.interfaces import IInterface
from zope.interface.verify import verifyObject

from fhirpath.enums import FHIR_VERSION
from fhirpath.utils import import_string
from fhirpath.utils import lookup_fhir_class
from fhirpath.utils import lookup_fhir_class_path
from fhirpath.utils import reraise

from .helpers import parse_json_str
from .interfaces import IFhirField
from .interfaces import IFhirFieldValue
from .interfaces import IFhirResource


__docformat__ = "restructuredtext"

FhirResourceType = NewType("FhirResourceType", type)


@implementer(IFhirFieldValue)
class FhirFieldValue(object):
    """FhirResourceValue is a proxy class for holding any object derrived from
    fhir.resources.resource.Resource"""

    __slot__ = ("_resource_obj",)

    def foreground_origin(self):
        """Return the original object of FHIR model that is proxied!"""
        if bool(self._resource_obj):
            return self._resource_obj
        else:
            return None

    def patch(self, patch_data):

        if not isinstance(patch_data, (list, tuple)):
            raise WrongType(
                "patch value must be list or tuple type! but got `{0}` type.".format(
                    type(patch_data)
                )
            )

        if not bool(self):
            raise Invalid(
                "None object cannot be patched! "
                "Make sure fhir resource value is not empty!"
            )
        try:
            patcher = jsonpatch.JsonPatch(patch_data)
            value = patcher.apply(self._resource_obj.as_json())

            new_value = self._resource_obj.__class__(value)

            object.__setattr__(self, "_resource_obj", new_value)

        except jsonpatch.JsonPatchException as exc:
            return reraise(Invalid, str(exc))

    def stringify(self, prettify=False):
        """ """
        params = {}
        if prettify:
            # will make little bit slow, so apply only if needed
            params["indent"] = 2

        return (
            self._resource_obj is not None
            and ujson.dumps(self._resource_obj.as_json(), **params)
            or ""
        )

    def _validate_object(self, obj: FhirResourceType = None):  # noqa: E999
        """ """
        if obj is None:
            return

        try:
            verifyObject(IFhirResource, obj, False)

        except (BrokenImplementation, BrokenMethodImplementation) as exc:
            return reraise(Invalid, str(exc))

        except DoesNotImplement as exc:
            msg = "Object must be derived from valid FHIR resource class!"
            msg += "But it is found that object is derived from `{0}`".format(
                obj.__class__.__module__ + "." + obj.__class__.__name__
            )
            msg += "\nOriginal Exception: {0!s}".format(exc)

            return reraise(WrongType, msg)

    def __init__(self, obj: FhirResourceType = None):
        """ """
        # Let's validate before value assignment!
        self._validate_object(obj)

        object.__setattr__(self, "_resource_obj", obj)

    def __getattr__(self, name):
        """Any attribute from FHIR Resource Object is accessible via this class"""
        try:
            return super(FhirFieldValue, self).__getattr__(name)
        except AttributeError:
            return getattr(self._resource_obj, name)

    def __getstate__(self):
        """ """
        odict = OrderedDict([("_resource_obj", self._resource_obj)])
        return odict

    def __setattr__(self, name, val):
        """This class kind of unmutable! All changes should be
        applied on FHIR Resource Object"""
        setattr(self._resource_obj, name, val)

    def __setstate__(self, odict):
        """ """
        for attr, value in odict.items():
            object.__setattr__(self, attr, value)

    def __str__(self):
        """ """
        return self.stringify()

    def __repr__(self):
        """ """
        if self.__bool__():
            return "<{0} object represents object of {1} at {2}>".format(
                self.__class__.__module__ + "." + self.__class__.__name__,
                self._resource_obj.__class__.__module__
                + "."
                + self._resource_obj.__class__.__name__,
                hex(id(self)),
            )
        else:
            return "<{0} object represents object of {1} at {2}>".format(
                self.__class__.__module__ + "." + self.__class__.__name__,
                None.__class__.__name__,
                hex(id(self)),
            )

    def __eq__(self, other):
        if not isinstance(other, FhirFieldValue):
            return NotImplemented
        return self._resource_obj == other._resource_obj

    def __ne__(self, other):
        equal = self.__eq__(other)
        if equal is NotImplemented:
            return NotImplemented
        return not equal

    def __bool__(self):
        """ """
        return bool(self._resource_obj is not None)

    __nonzero__ = __bool__


FhirFieldValueType = NewType("FhirFieldValueType", FhirFieldValue)


@implementer(IFhirField, IFromUnicode)
class FhirField(Object):
    """FhirResource also known as FHIR field is the schema
    field derrived from z3c.form's field.

    It takes all initilial arguments those are derrived from standard schema field,
    with additionally
    ``model``, ``resource_type`` and ``resource_interface``

    .. note::
        field name must be start with lowercase name of FHIR Resource.
    """

    _type = FhirFieldValue
    _resource_class = None
    _resource_interface_class = None

    def __init__(
        self,
        resource_class=None,
        resource_interface=None,
        resource_type=None,
        fhir_version=None,
        **kw,
    ):
        """
        :arg resource_class: dotted path of FHIR Resource class

        :arg resource_type:

        :arg resource_interface
        """

        self.schema = IFhirFieldValue

        self._init(
            resource_class, resource_interface, resource_type, fhir_version, **kw
        )

        if "default" in kw:
            default = kw["default"]

            if isinstance(default, str):
                kw["default"] = self.from_unicode(default)

            elif isinstance(default, dict):
                kw["default"] = self.from_dict(default)

        super(FhirField, self).__init__(schema=self.schema, **kw)

    def from_unicode(self, str_val):
        """ """
        json_dict = parse_json_str(str_val)

        return self.from_dict(json_dict)

    def from_dict(self, dict_value):
        """ """
        if dict_value is None:
            value = None
        else:
            value = self._from_dict(dict_value)
        # do validation now
        self.validate(value)
        return value

    def _init(
        self,
        resource_class,
        resource_interface,
        resource_type,
        fhir_version,
        **kw
    ):
        """ """
        if "default" in kw:

            if (
                isinstance(kw["default"], (str, dict)) or kw["default"] is None
            ) is False:
                msg = (
                    "Only dict or string or None is accepted as "
                    "default value but got {0}".format(type(kw["default"]))
                )

                raise Invalid(msg)

        field_attributes = get_fields(IFhirField)

        attribute = field_attributes["resource_class"].bind(self)
        if resource_class is None:
            attribute.validate(resource_class)
            attribute_val = None
        else:
            attribute_val = attribute.from_unicode(resource_class)
        attribute.set(self, attribute_val)

        attribute = field_attributes["resource_interface"].bind(self)
        if resource_interface is None:
            attribute.validate(resource_interface)
            attribute_val = None
        else:
            attribute_val = attribute.from_unicode(resource_interface)
        attribute.set(self, attribute_val)

        attribute = field_attributes["resource_type"].bind(self)
        if resource_type is None:
            attribute.validate(resource_type)
            attribute_val = None
        else:
            attribute_val = attribute.from_unicode(resource_type)
        attribute.set(self, attribute_val)

        attribute = field_attributes["fhir_version"].bind(self)
        if fhir_version is None:
            attribute.validate(fhir_version)
            attribute_val = None
        else:
            attribute_val = attribute.from_unicode(fhir_version)
            # just for ensure correct value
            FHIR_VERSION[attribute_val]
        attribute.set(self, attribute_val)

        if self.resource_type and self.resource_class is not None:
            raise Invalid(
                "Either `resource_class` or `resource_type` value is acceptable! "
                "you cannot provide both!"
            )

        if self.resource_class:
            try:
                klass = import_string(self.resource_class)
                self.ensure_fhir_abstract(klass)

            except ImportError:
                msg = (
                    "Invalid FHIR Resource class `{0}`! "
                    "Please check the module or class name."
                ).format(self.resource_class)

                return reraise(Invalid, msg)

            if not IFhirResource.implementedBy(klass):

                raise Invalid(
                    "{0!r} must be valid resource class from fhir.resources".format(
                        klass
                    )
                )
            self._resource_class = klass

        if self.resource_type:

            try:
                self._resource_class = implementer(IFhirResource)(
                    lookup_fhir_class(self.resource_type)
                )
            except ImportError:
                msg = "{0} is not valid fhir resource type!".format(self.resource_type)
                return reraise(Invalid, msg)

        if self.resource_interface:
            try:
                klass = implementer(IFhirResource)(
                    import_string(self.resource_interface)
                )
            except ImportError:
                msg = (
                    "Invalid FHIR Resource Interface`{0}`! "
                    "Please check the module or class name."
                ).format(self.resource_interface)
                return reraise(Invalid, msg)

            if not IInterface.providedBy(klass):
                raise WrongType("An interface is required", klass, self.__name__)

            if klass is not IFhirResource and not issubclass(klass, IFhirResource):
                msg = "`{0!r}` must be derived from {1}".format(
                    klass,
                    IFhirResource.__module__ + "." + IFhirResource.__class__.__name__,
                )

                raise Invalid(msg)

            self._resource_interface_class = klass

    def _pre_value_validate(self, fhir_json):
        """ """
        if isinstance(fhir_json, str):
            fhir_dict = parse_json_str(fhir_json).copy()

        elif isinstance(fhir_json, dict):
            fhir_dict = fhir_json.copy()

        else:
            raise WrongType(
                "Only dict type data is allowed but got `{0}` type data!".format(
                    type(fhir_json)
                )
            )

        if "resourceType" not in fhir_dict.keys() or "id" not in fhir_dict.keys():
            raise Invalid(
                "Invalid FHIR resource json is provided!\n{0}".format(fhir_json)
            )

    def ensure_fhir_abstract(self, klass):
        """ """
        yes = False
        for cls in inspect.getmro(klass):
            if cls.__name__ == "FHIRAbstractBase":
                yes = True
                break
        if not yes:
            raise Invalid(f"{klass} has not been derrived from FHIRAbstractBase class")

    def _from_dict(self, dict_value):
        """ """
        self._pre_value_validate(dict_value)
        klass = self._resource_class

        if klass is None:
            # relay on json value for resource type
            klass = implementer(IFhirResource)(
                lookup_fhir_class(dict_value["resourceType"])
            )

        # check constraint
        if klass.resource_type != dict_value.get("resourceType"):
            raise ConstraintNotSatisfied(
                "Fhir Resource mismatched with provided resource type!\n"
                "`{0}` resource type is permitted but got `{1}`".format(
                    klass.resource_type, dict_value.get("resourceType")
                )
            )

        value = FhirFieldValue(obj=klass(dict_value))

        return value

    def _validate(self, value):
        """ """
        super(FhirField, self)._validate(value)

        if self.resource_interface:
            try:
                verifyObject(
                    self._resource_interface_class, value.foreground_origin(), False
                )

            except (
                BrokenImplementation,
                BrokenMethodImplementation,
                DoesNotImplement,
            ) as exc:

                return reraise(Invalid, str(exc))

        if self.resource_type and value.resource_type != self.resource_type:
            msg = (
                "Resource type must be `{0}` but we got {1} " "which is not allowed!"
            ).format(self.resource_type, value.resource_type)
            raise ConstraintNotSatisfied(msg)

        if self.resource_class:
            klass = self._resource_class

            if value.foreground_origin() is not None and not isinstance(
                value.foreground_origin(), klass
            ):
                msg = (
                    "Wrong fhir resource value is provided! "
                    "Value should be object of {0!r} but got {1!r}".format(
                        klass, value.foreground_origin().__class__
                    )
                )

                raise WrongContainedType(msg)

        if value.foreground_origin() is not None:
            try:
                value.foreground_origin().as_json()
            except (FHIRValidationError, TypeError) as exc:
                msg = (
                    "There is invalid element inside " "fhir model object.\n{0!s}"
                ).format(exc)

                return reraise(Invalid, msg)


@configure.value_deserializer(IFhirField)
def fhir_field_deserializer(fhirfield, value, context=None):
    """ """
    if value in (None, ""):
        return None

    if isinstance(value, str):
        return IFhirField(fhirfield).from_unicode(value)
    elif isinstance(value, dict):
        return IFhirField(fhirfield).from_dict(value)
    else:
        raise ValueError(
            (
                "Invalid data type({0}) provided! only dict or "
                "string data type is accepted."
            ).format(type(value))
        )


@configure.value_serializer(IFhirFieldValue)
def fhir_field_value_serializer(value):
    """ """
    if value:
        value = value.as_json()
    else:
        value = None

    return value


@configure.adapter(
    for_=(IFhirField, Interface, Interface), provides=ISchemaFieldSerializeToJson
)
class DefaultFhirFieldSchemaSerializer(DefaultSchemaFieldSerializer):
    @property
    def field_type(self):
        return "FhirField"


def fhir_field_from_schema(
    schema: Interface, resource_type: str = None
) -> Union[FhirField, None]:
    """ """
    index_fields: dict

    if resource_type:
        index_fields = directives.merged_tagged_value_dict(schema, directives.index.key)

    for name, field in get_fields_in_order(schema):

        if IFhirField.providedBy(field):
            if resource_type:
                catalog_info = index_fields.get(name, None)
                if catalog_info is None:
                    continue
                if catalog_info.get("resource_type", None) is None:
                    continue

                if catalog_info["resource_type"] != resource_type:
                    continue

            return field

    return None


_RESOURCE_TYPE_TO_FHIR_FIELD_CACHE: dict = {}


def fhir_field_from_resource_type(
    resource_type: str, cache: bool = True
) -> Union[dict, None]:
    """ """
    global _RESOURCE_TYPE_TO_FHIR_FIELD_CACHE

    if cache and resource_type in _RESOURCE_TYPE_TO_FHIR_FIELD_CACHE:

        return _RESOURCE_TYPE_TO_FHIR_FIELD_CACHE[resource_type]

    # validate_resource_type(resource_type)
    klass_path = lookup_fhir_class_path(resource_type)
    if klass_path is None:
        raise Invalid(f"{resource_type} is not valid FHIR Resource")

    factories = [x[1] for x in get_utilities_for(IResourceFactory)]

    fields: dict = {}

    for factory in factories:
        field = fhir_field_from_schema(factory.schema, resource_type)

        if field is not None:

            if field.getName() not in fields:
                fields[field.getName()] = {"field": field, "types": list()}
            if factory.type_name not in fields[field.getName()]["types"]:
                fields[field.getName()]["types"].append(factory.type_name)

            break

        # Try find from behavior
        for schema in factory.behaviors or ():
            field = fhir_field_from_schema(schema)
            if field is not None:
                if field.__name__ not in fields:
                    fields[field.__name__] = {"field": field, "types": list()}
                if factory.type_name not in fields[field.__name__]["types"]:
                    fields[field.__name__]["types"].append(factory.type_name)

    if fields:
        # xxx: do validation over multiple fields or other stuff?
        _RESOURCE_TYPE_TO_FHIR_FIELD_CACHE[resource_type] = fields

        return _RESOURCE_TYPE_TO_FHIR_FIELD_CACHE[resource_type]

    return None
