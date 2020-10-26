import logging
from collections import defaultdict

from fhirpath.enums import FHIR_VERSION

ignored_datatype = [
    "markdown",
    "UsageContext",
    "TriggerDefinition",
    "DataRequirement",
    "ParameterDefinition",
    "MarketingStatus",
    "ProdCharacteristic",
    "SampledData",
    "Contributor",
    "ElementDefinition",
    "ProductShelfLife",
    "Resource",
    "Extension",
    "SubstanceAmount",
]


def build_elements_paths(resources_elements):
    """ """
    resources_elements_paths = defaultdict()
    default_paths = extract_elements_paths(resources_elements.pop("Resource"))
    default_domain_paths = extract_elements_paths(
        resources_elements.pop("DomainResource")
    )
    for resource, elements in resources_elements.items():
        paths = extract_elements_paths(elements)
        apply_default_paths(resource, default_paths, paths)
        apply_default_paths(resource, default_domain_paths, paths)
        resources_elements_paths[resource] = paths

    return resources_elements_paths


def extract_elements_paths(elements):
    """ """
    paths = list()

    for el in elements:
        if el.is_main_profile_element:
            continue
        if len(el.definition.types) == 0:
            continue

        if el.path.endswith("[x]"):
            assert len(el.definition.types) > 1
            for ty in el.definition.types:
                addon = ty.code[0].upper() + ty.code[1:]
                paths.append(
                    (el.path.replace("[x]", addon), ty.code, (el.n_max != "1"))
                )
        else:
            paths.append((el.path, el.definition.types[0].code, (el.n_max != "1")))
    return paths


def apply_default_paths(resource, defaults, container):
    """ """
    for path_, code, multiple in defaults:
        parts = path_.split(".")
        _path = ".".join([resource] + list(parts[1:]))
        container.append((_path, code, multiple))


def create_resource_mapping(elements_paths_def, fhir_es_mappings):
    """ """
    mapped = dict()

    # this generator function iterates over the list of elements definitions and groups
    # children elements with their parents to reflect thbe nested resource structure.
    def iterate_elements():
        mapped_elements = list()
        for path, code, multiple in elements_paths_def:
            if path not in mapped_elements:
                children = [
                    x
                    for x in elements_paths_def
                    if x[0].startswith(path) and x[0] != path
                ]
                mapped_elements.extend([path, *[c[0] for c in children]])
                yield path, code, multiple, children

    for path, code, multiple, children in iterate_elements():
        name = path.split(".")[-1]
        try:
            map_ = fhir_es_mappings[code].copy()
        except KeyError:
            # if the element is of type BackboneElement, it means that it has no
            # external definition
            # and needs to be mapped dynamically based on its inline definition.
            if code == "BackboneElement":
                map_ = {
                    "type": "nested",
                    "properties": create_resource_mapping(children, fhir_es_mappings),
                }
            elif code in ignored_datatype:
                logging.debug(
                    f"{path} won't be indexed in elasticsearch: type {code} is ignored"
                )
                continue
            else:
                logging.debug(
                    f"{path} won't be indexed in elasticsearch: type {code} is unknown"
                )
                raise

        if multiple and "type" not in map_:
            map_.update({"type": "nested"})

        mapped[name] = map_

    mapped["resourceType"] = fhir_es_mappings["code"].copy()
    return mapped


def fhir_types_mapping(
    fhir_release: str,
    reference_analyzer=None,
    token_normalizer=None,
):
    Boolean = {"type": "boolean", "store": False}
    Float = {"type": "float", "store": False}
    Integer = {"type": "integer", "store": False}
    Token = {
        "type": "keyword",
        "index": True,
        "store": False,
        "fields": {
            # index the raw text without normalization for exact matching
            "raw": {"type": "keyword"}
        },
    }
    if token_normalizer:
        Token.update({"normalizer": token_normalizer})

    ReferenceToken = {
        "type": "text",
        "index": True,
        "store": False,
    }
    if reference_analyzer:
        ReferenceToken.update({"analyzer": reference_analyzer})

    Text = {
        "type": "keyword",
        "index": True,
        "store": False,
        "fields": {
            # re-index the raw text without normalization for exact matching
            "raw": {"type": "keyword"},
        },
    }

    SearchableText = {
        "type": "text",
        "index": True,
        "analyzer": "standard",
        "store": False,
    }

    Date = {
        "type": "date",
        "format": "date_time_no_millis||date_optional_time",
        "store": False,
    }
    Time = {"type": "date", "format": "basic_t_time_no_millis", "store": False}

    Attachment = {
        "properties": {"url": Token, "language": Token, "title": Text, "creation": Date}
    }

    Coding = {"properties": {"system": Token, "code": Token, "display": Token}}

    CodeableConcept = {
        "properties": {
            "text": Text,
            "coding": {"type": "nested", "properties": Coding["properties"]},
        }
    }

    Period = {"properties": {"start": Date, "end": Date}}
    Timing = {"properties": {"event": Date, "code": CodeableConcept}}

    Identifier = {
        "properties": {
            "use": Token,
            "system": Token,
            "value": Token,
            "type": {"properties": {"text": Text}},
        }
    }

    Reference = {"properties": {"reference": ReferenceToken, "identifier": Identifier}}

    Quantity = {
        "properties": {"value": Float, "code": Token, "system": Token, "unit": Token}
    }

    Money = {"properties": {"value": Float, "currency": Token}}
    Money_STU3 = Quantity
    Range = {"properties": {"high": Quantity, "low": Quantity}}
    Ratio = {"properties": {"numerator": Quantity, "denominator": Quantity}}

    Age = Quantity
    Address = {
        "properties": {
            "city": Token,
            "country": Token,
            "postalCode": Token,
            "state": Token,
            "use": Token,
        }
    }

    HumanName = {
        "properties": {
            "family": Token,
            "text": Text,
            "prefix": Token,
            "given": Token,
            "use": Token,
            "period": Period,
        },
    }

    Duration = Quantity

    ContactPoint = {
        "properties": {
            "period": Period,
            "rank": Integer,
            "system": Token,
            "use": Token,
            "value": Text,
        }
    }

    ContactDetail = {
        "properties": {
            "name": Token,
            "telecom": {**ContactPoint, "type": "nested"},  # type: ignore
        }
    }

    Annotation = {
        "properties": {
            "authorReference": Reference,
            "authorString": Text,
            "text": Text,
            "time": Date,
        }
    }

    Dosage = {
        "properties": {
            "asNeededBoolean": Boolean,
            "asNeededCodeableConcept": CodeableConcept,
            "site": CodeableConcept,
            "text": Text,
            "timing": Timing,
            "patientInstruction": Text,
            "doseAndRate": {
                "properties": {
                    "doseQuantity": Quantity,
                    "type": CodeableConcept,
                    "rateRatio": Ratio,
                    "rateRange": Range,
                    "rateQuantity": Quantity,
                }
            },
            "maxDosePerPeriod": Ratio,
            "maxDosePerAdministration": Quantity,
            "maxDosePerLifetime": Quantity,
        }
    }
    Dosage_STU3 = {
        "properties": {
            "asNeededBoolean": Boolean,
            "asNeededCodeableConcept": CodeableConcept,
            "doseQuantity": Quantity,
            "doseRange": Range,
            "site": CodeableConcept,
            "text": Text,
            "timing": Timing,
        }
    }

    RelatedArtifact = {
        "properties": {
            "type": Token,
            "url": Token,
            "resource": Reference,
            "label": Text,
            "display": Text,
        }
    }

    RelatedArtifact_STU3 = {
        "properties": {"type": Token, "url": Token, "resource": Reference}
    }

    Signature = {
        "properties": {
            "type": Coding,
            "when": Date,
            "who": Reference,
            "targetFormat": Token,
            "sigFormat": Token,
            "onBehalfOf": Reference,
        }
    }

    Signature_STU3 = {
        "properties": {
            "contentType": Token,
            "when": Date,
            "whoReference": Reference,
            "whoUri": Token,
        }
    }
    Population = {
        "properties": {
            "ageRange": Range,
            "ageCodeableConcept": CodeableConcept,
            "gender": CodeableConcept,
            "race": CodeableConcept,
            "physiologicalCondition": CodeableConcept,
        }
    }

    Meta = {
        "properties": {
            "versionId": Token,
            "lastUpdated": Date,
            "profile": Token,
            "tag": {**Coding, "type": "nested", "include_in_root": True},
        }
    }

    Expression = {
        "properties": {
            "description": Token,
            "name": Token,
            "language": Token,
            "expression": Token,
            "reference": Token,
        }
    }

    Narrative = {"properties": {"status": Token, "div": SearchableText}}

    Count = Quantity
    Distance = Quantity

    return {
        "boolean": Boolean,
        "base64Binary": Token,
        "integer": Integer,
        "string": Text,
        "decimal": Float,
        "uri": Token,
        "url": Token,
        "canonical": Token,
        "instant": Date,
        "date": Date,
        "dateTime": Date,
        "time": Time,
        "code": Token,
        "oid": Token,
        "id": Token,
        "unsignedInt": Integer,
        "positiveInt": Integer,
        "uuid": Token,
        "Attachment": Attachment,
        "Coding": Coding,
        "CodeableConcept": CodeableConcept,
        "Quantity": Quantity,
        "Distance": Distance,
        "Count": Count,
        "Money": {FHIR_VERSION.STU3.name: Money_STU3, FHIR_VERSION.R4.name: Money}[
            fhir_release
        ],
        "Duration": Duration,
        "Range": Range,
        "Ratio": Ratio,
        "Period": Period,
        "Identifier": Identifier,
        "HumanName": HumanName,
        "Address": Address,
        "ContactPoint": ContactPoint,
        "Timing": Timing,
        "Dosage": {FHIR_VERSION.STU3.name: Dosage_STU3, FHIR_VERSION.R4.name: Dosage}[
            fhir_release
        ],
        "Meta": Meta,
        "Annotation": Annotation,
        "ContactDetail": ContactDetail,
        "Age": Age,
        "Reference": Reference,
        "RelatedArtifact": {
            FHIR_VERSION.STU3.name: RelatedArtifact_STU3,
            FHIR_VERSION.R4.name: RelatedArtifact,
        }[fhir_release],
        "Signature": {
            FHIR_VERSION.STU3.name: Signature_STU3,
            FHIR_VERSION.R4.name: Signature,
        }[fhir_release],
        "Population": Population,
        "Narrative": Narrative,
        "Expression": Expression,
    }
