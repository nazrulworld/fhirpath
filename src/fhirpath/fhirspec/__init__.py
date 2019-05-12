# _*_ coding: utf-8 _*_
"""FHIR Specification: http://www.hl7.org/fhir/"""
from fhirpath.thirdparty import attrdict

from .spec import FHIRSpec  # noqa: F401


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


DEFAULT_SETTINGS = attrdict(
    base_url="http://hl7.org/fhir",
    classmap={
        "Any": "Resource",
        # to avoid Practinioner.role and PractitionerRole generating the same class
        "Practitioner.role": "PractRole",
        "boolean": "bool",
        "integer": "int",
        "positiveInt": "int",
        "unsignedInt": "int",
        "date": "FHIRDate",
        "dateTime": "FHIRDate",
        "instant": "FHIRDate",
        "time": "FHIRDate",
        "decimal": "float",
        "string": "str",
        "markdown": "str",
        "id": "str",
        "code": "str",  # for now we're not generating enums for these
        "uri": "str",
        "url": "str",
        "canonical": "str",
        "oid": "str",
        "uuid": "str",
        "xhtml": "str",
        "base64Binary": "str",
    },
    # Classes to be replaced with different ones at resource rendering time
    replacemap={
        "Reference": "FHIRReference"  # `FHIRReference` adds dereferencing capabilities
    },
    # Which class names are native to the language (or can be treated this way)
    natives=["bool", "int", "float", "str", "dict"],
    # Which classes are to be expected from JSON decoding
    jsonmap={
        "str": "str",
        "int": "int",
        "bool": "bool",
        "float": "float",
        "FHIRDate": "str",
    },
    jsonmap_default="dict",
    # Properties that need to be renamed because of language keyword conflicts
    reservedmap={
        "for": "for_fhir",
        "from": "from_fhir",
        "class": "class_fhir",
        "import": "import_fhir",
        "global": "global_fhir",
        "assert": "assert_fhir",
        "except": "except_fhir",
    },
    # For enum codes where a computer just cannot generate reasonable names
    enum_map={"=": "eq", "<": "lt", "<=": "lte", ">": "gt", ">=": "gte", "*": "max"},
    # If you want to give specific names to enums based on their URI
    enum_namemap={
        "http://hl7.org/fhir/contracttermsubtypecodes": "ContractTermSubtypeCodes",
        "http://hl7.org/fhir/coverage-exception": "CoverageExceptionCodes",
        "http://hl7.org/fhir/resource-type-link": "ResourceTypeLink",
    },
    # Settings for classes and resources
    default_base={
        "complex-type": "FHIRAbstractBase",  # the class to use for "Element" types
        "resource": "FHIRAbstractResource",  # the class to use for "Resource" types
    },
    # whether all resource paths (i.e. modules) should be lowercase
    resource_modules_lowercase=True,
    camelcase_classes=True,  # whether class name generation should use CamelCase
    camelcase_enums=True,  # whether names for enums should be camelCased
    # if True, backbone class names prepend their parent's class name
    backbone_class_adds_parent=True,
    manual_profiles=(
        # Primitive Data Types
        "boolean",
        "string",
        "base64Binary",
        "code",
        "id",
        "decimal",
        "integer",
        "unsignedInt",
        "positiveInt",
        "uri",
        "url",
        "canonical" "oid",
        "uuid",
        "date",
        "dateTime",
        "instant",
        "time",
        "markdown",
        # End Primitive
        "FHIRSearch",
        "FHIRAbstractBase",
        "FHIRAbstractResource",
    ),
)
