import os
import pathlib


"""Variable Start Here """
BASE_PATH = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = "downloads"
# classmap
CLASS_MAP = {
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
}

# replacemap
# Classes to be replaced with different ones at resource rendering time
REPLACE_MAP = {
    "Reference": "FHIRReference"  # `FHIRReference` adds differencing capabilities
}
# natives
# Which class names are native to the language (or can be treated this way)
NATIVES = ["bool", "int", "float", "str", "dict"]

# jsonmap
# Which classes are to be expected from JSON decoding
JSON_MAP = {
    "str": "str",
    "int": "int",
    "bool": "bool",
    "float": "float",
    "FHIRDate": "str",
}
# jsonmap_default
JSON_MAP_DEFAULT = "dict"

# reservedmap
# Properties that need to be renamed because of language keyword conflicts
RESERVED_MAP = {
    "for": "for_fhir",
    "from": "from_fhir",
    "class": "class_fhir",
    "import": "import_fhir",
    "global": "global_fhir",
    "assert": "assert_fhir",
    "except": "except_fhir",
}

# enum_map
# For enum codes where a computer just cannot generate reasonable names
ENUM_MAP = {"=": "eq", "<": "lt", "<=": "lte", ">": "gt", ">=": "gte", "*": "max"}

# enum_namemap
# If you want to give specific names to enums based on their URI
ENUM_NAME_MAP = {
    "http://hl7.org/fhir/contracttermsubtypecodes": "ContractTermSubtypeCodes",
    "http://hl7.org/fhir/coverage-exception": "CoverageExceptionCodes",
    "http://hl7.org/fhir/resource-type-link": "ResourceTypeLink",
}

# write_resources
# Whether and where to put the generated class models
WRITE_RESOURCES = False


# write_unittests
# Whether and where to write unit tests
WRITE_UNITTESTS = False

# Settings for classes and resources
# default_base
DEFAULT_BASES = {
    # the class to use for "Element" types
    "complex-type": "FHIRAbstractBase",
    # the class to use for "Resource" types
    "resource": "FHIRAbstractResource",
}

# manual_profiles
# All these files should be copied to `RESOURCE_TARGET_DIRECTORY`:
# tuples of (path/to/file, module, array-of-class-names)
# If the path is None, no file will be copied but the
# class names will still be recognized and it is assumed the class is present.
MANUAL_PROFILES = [
    (
        "templates/fhirabstractbase.py",
        "fhirabstractbase",
        [
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
            "oid",
            "uuid",
            "canonical",
            "url",
            "markdown",
            "FHIRAbstractBase",
        ],
    ),
    (
        "templates/fhirabstractresource.py",
        "fhirabstractresource",
        ["FHIRAbstractResource"],
    ),
    ("templates/fhirreference.py", "fhirreference", ["FHIRReference"]),
    ("templates/fhirdate.py", "fhirdate", ["date", "dateTime", "instant", "time"],),
    ("templates/fhirsearch.py", "fhirsearch", ["FHIRSearch"]),
]
FHIR_VALUESETS_FILE_NAME = "valuesets.min.json"
FHIR_PROFILES_FILE_NAMES = ["profiles-resources.min.json", "profiles-types.min.json"]
CAMELCASE_CLASSES = True
CAMELCASE_ENUMS = True
BACKBONE_CLASS_ADDS_PARENT = True
RESOURCE_MODULE_LOWERCASE = True
