# _*_ coding: utf-8 _*_
"""Most of codes are copied from https://github.com/nazrulworld/fhir-parser
and modified in terms of styling, unnesessary codes cleanup
(those are not relevant for this package)
"""
import datetime
import io
import json
import logging
import os
import pathlib
import re
from copy import copy
from collections import defaultdict

from fhirpath.interfaces import IStorage
from fhirpath.thirdparty import attrdict
from fhirpath.utils import expand_path
from fhirpath.utils import reraise


logger = logging.getLogger("fhirpath.fhrspec")

# allow to skip some profiles by matching against their url (used while WiP)
skip_because_unsupported = [r"SimpleQuantity"]


class FHIRSpec(object):
    """ The FHIR specification."""

    def __init__(self, directory: str, settings: attrdict):
        """ """
        source = pathlib.Path(expand_path(directory))
        assert source.is_dir()
        self.directory = source

        assert settings is not None
        self.settings = settings

        self.info = FHIRVersionInfo(self, self.directory)

        self.valuesets = {}  # system-url: FHIRValueSet()
        self.codesystems = {}  # system-url: FHIRCodeSystem()
        self.profiles = {}  # profile-name: FHIRStructureDefinition()

        self.prepare()
        self.read_profiles()
        self.finalize()

    def prepare(self):
        """ Run actions before starting to parse profiles.
        """
        self.read_valuesets()
        self.handle_manual_profiles()

    def read_bundle_resources(self, filename):
        """ Return an array of the Bundle's entry's "resource" elements.
        """
        logger.info("Reading {}".format(filename))
        filepath = os.path.join(self.directory, filename)
        with io.open(filepath, encoding="utf-8") as handle:
            parsed = json.load(handle)
            if "resourceType" not in parsed:
                raise Exception(
                    'Expecting "resourceType" to be present, but is not in {}'.format(
                        filepath
                    )
                )
            if "Bundle" != parsed["resourceType"]:
                raise Exception('Can only process "Bundle" resources')
            if "entry" not in parsed:
                raise Exception(
                    "There are no entries in the Bundle at {}".format(filepath)
                )

            return [e["resource"] for e in parsed["entry"]]

    # MARK: Managing ValueSets and CodeSystems
    def read_valuesets(self):
        filename = getattr(self.settings, "valuesets_filename", "valuesets.json")
        resources = self.read_bundle_resources(filename)
        for resource in resources:
            if "ValueSet" == resource["resourceType"]:
                assert "url" in resource
                self.valuesets[resource["url"]] = FHIRValueSet(self, resource)
            elif "CodeSystem" == resource["resourceType"]:
                assert "url" in resource
                if "content" in resource and "concept" in resource:
                    self.codesystems[resource["url"]] = FHIRCodeSystem(self, resource)
                else:
                    logger.warning(
                        "CodeSystem with no concepts: {0}".format(resource["url"])
                    )
        logger.info(
            "Found {0} ValueSets and {1} CodeSystems".format(
                len(self.valuesets), len(self.codesystems)
            )
        )

    def valueset_with_uri(self, uri):
        assert uri
        return self.valuesets.get(uri)

    def codesystem_with_uri(self, uri):
        assert uri
        return self.codesystems.get(uri)

    # MARK: Handling Profiles
    def read_profiles(self):
        """ Find all (JSON) profiles and instantiate into FHIRStructureDefinition.
        """
        resources = []
        filenames = getattr(
            self.settings,
            "profiles_filenames",
            ["profiles-types.json", "profiles-resources.json"],
        )
        for filename in filenames:
            bundle_res = self.read_bundle_resources(filename)
            for resource in bundle_res:
                if "StructureDefinition" == resource["resourceType"]:
                    resources.append(resource)
                else:
                    logger.debug(
                        "Not handling resource of type {}".format(
                            resource["resourceType"]
                        )
                    )

        # create profile instances
        for resource in resources:
            profile = FHIRStructureDefinition(self, resource)
            for pattern in skip_because_unsupported:
                if re.search(pattern, profile.url) is not None:
                    logger.info('Skipping "{}"'.format(resource["url"]))
                    profile = None
                    break

            if profile is not None and self.found_profile(profile):
                profile.process_profile()

    def found_profile(self, profile):
        if not profile or not profile.name:
            raise Exception("No name for profile {}".format(profile))
        if profile.name.lower() in self.profiles:
            logger.debug('Already have profile "{}", discarding'.format(profile.name))
            return False

        self.profiles[profile.name.lower()] = profile
        return True

    def handle_manual_profiles(self):
        """ Creates in-memory representations for all our manually defined
        profiles.
        """
        for name in self.settings.manual_profiles:

            profile = FHIRStructureDefinition(self, None)
            profile.is_manual = True
            prof_dict = {"name": name, "differential": {"element": [{"path": name}]}}

            profile.structure = FHIRStructureDefinitionStructure(profile, prof_dict)
            if self.found_profile(profile):
                profile.process_profile()

    def finalize(self):
        """ Should be called after all profiles have been parsed and allows
        to perform additional actions, like looking up class implementations
        from different profiles.
        """
        for key, prof in self.profiles.items():
            prof.finalize()

    # MARK: Naming Utilities
    def as_module_name(self, name):
        return (
            name.lower() if name and self.settings.resource_modules_lowercase else name
        )

    def as_class_name(self, classname, parent_name=None):
        if not classname or 0 == len(classname):
            return None

        # if we have a parent, do we have a mapped class?
        pathname = f"{parent_name}.{classname}" if parent_name is not None else None
        if pathname is not None and pathname in self.settings.classmap:
            return self.settings.classmap[pathname]

        # is our plain class mapped?
        if classname in self.settings.classmap:
            return self.settings.classmap[classname]

        # CamelCase or just plain
        if self.settings.camelcase_classes:
            return classname[:1].upper() + classname[1:]
        return classname

    def class_name_for_type(self, type_name, parent_name=None):
        return self.as_class_name(type_name, parent_name)

    def class_name_for_type_if_property(self, type_name):
        classname = self.class_name_for_type(type_name)
        if not classname:
            return None
        return self.settings.replacemap.get(classname, classname)

    def class_name_for_profile(self, profile_name):
        if not profile_name:
            return None
        # TODO need to figure out what to do with this later.
        # Annotation author supports multiples types that caused this to fail
        if isinstance(profile_name, (list,)) and len(profile_name) > 0:
            classnames = []
            for name_part in profile_name:
                classnames.append(
                    self.as_class_name(name_part.split("/")[-1])
                )  # may be the full Profile URI
            return classnames
        type_name = profile_name.split("/")[
            -1
        ]  # may be the full Profile URI, like http://hl7.org/fhir/Profile/MyProfile
        return self.as_class_name(type_name)

    def class_name_is_native(self, class_name):
        return class_name in self.settings.natives

    def safe_property_name(self, prop_name):
        return self.settings.reservedmap.get(prop_name, prop_name)

    def safe_enum_name(self, enum_name, ucfirst=False):
        assert enum_name, "Must have a name"
        name = self.settings.enum_map.get(enum_name, enum_name)
        parts = re.split(r"\W+", name)
        if self.settings.camelcase_enums:
            name = "".join([n[:1].upper() + n[1:] for n in parts])
            if not ucfirst and name.upper() != name:
                name = name[:1].lower() + name[1:]
        else:
            name = "_".join(parts)
        return self.settings.reservedmap.get(name, name)

    def json_class_for_class_name(self, class_name):
        return self.settings.jsonmap.get(class_name, self.settings.jsonmap_default)

    def writable_profiles(self):
        """ Returns a list of `FHIRStructureDefinition` instances.
        """
        profiles = []
        for key, profile in self.profiles.items():
            if not profile.is_manual:
                profiles.append(profile)
        return profiles


class FHIRVersionInfo(object):
    """ The version of a FHIR specification."""

    def __init__(self, spec: FHIRSpec, directory: pathlib.Path = None):
        """ """
        self.spec = spec

        if directory is None:
            directory = self.spec.directory

        now = datetime.date.today()
        self.date = now.isoformat()
        self.year = now.year

        self.version = None
        infofile = directory / "version.info"
        self.read_version(infofile)

    def read_version(self, filepath: pathlib.Path):
        """ """
        assert filepath.is_file()
        with io.open(str(filepath), "r", encoding="utf-8") as fp:
            text = fp.read()
            for line in text.split("\n"):
                if "=" in line:
                    (n, v) = line.strip().split("=", 2)
                    if "FhirVersion" == n:
                        self.version = v


class FHIRValueSet(object):
    """ Holds on to ValueSets bundled with the spec."""

    def __init__(self, spec, set_dict):
        self.spec = spec
        self.definition = set_dict
        self._enum = None

    @property
    def enum(self):
        """ Returns FHIRCodeSystem if this valueset can be represented by one.
        """
        if self._enum is not None:
            return self._enum

        compose = self.definition.get("compose")
        if compose is None:
            raise Exception("Currently only composed ValueSets are supported")
        if "exclude" in compose:
            raise Exception("Not currently supporting 'exclude' on ValueSet")
        include = compose.get("include")
        if 1 != len(include):
            logger.warn(
                "Ignoring ValueSet with more than 1 includes ({}: {})".format(
                    len(include), include
                )
            )
            return None

        system = include[0].get("system")
        if system is None:
            return None

        # alright, this is a ValueSet with 1 include and a system,
        # is there a CodeSystem?
        cs = self.spec.codesystem_with_uri(system)
        if cs is None or not cs.generate_enum:
            return None

        # do we only allow specific concepts?
        restricted_to = []
        concepts = include[0].get("concept")
        if concepts is not None:
            for concept in concepts:
                assert "code" in concept
                restricted_to.append(concept["code"])

        self._enum = {
            "name": cs.name,
            "restricted_to": restricted_to if len(restricted_to) > 0 else None,
        }
        return self._enum


class FHIRCodeSystem(object):
    """ Holds on to CodeSystems bundled with the spec.
    """

    def __init__(self, spec: FHIRSpec, resource: dict):
        """ """
        assert "content" in resource

        self.spec = spec
        self.definition = resource
        self.url = resource.get("url")
        if self.url in self.spec.settings.enum_namemap:
            self.name = self.spec.settings.enum_namemap[self.url]
        else:
            self.name = self.spec.safe_enum_name(resource.get("name"), ucfirst=True)
        self.codes = None
        self.generate_enum = False
        concepts = self.definition.get("concept", [])

        if resource.get("experimental"):
            return
        self.generate_enum = "complete" == resource["content"]
        if not self.generate_enum:
            logger.debug(
                'Will not generate enum for CodeSystem "{0}"'
                " whose content is {1}".format(self.url, resource["content"])
            )
            return

        assert concepts, 'Expecting at least one code for "complete" CodeSystem'
        if len(concepts) > 200:
            self.generate_enum = False
            logger.info(
                'Will not generate enum for CodeSystem "{0}"'
                "because it has > 200 ({1}) concepts".format(self.url, len(concepts))
            )
            return

        self.codes = self.parsed_codes(concepts)

    def parsed_codes(self, codes, prefix=None):
        found = []
        for c in codes:
            if re.match(r"\d", c["code"][:1]):
                self.generate_enum = False
                logger.info(
                    'Will not generate enum for CodeSystem "{0}"'
                    " because at least one concept code starts with a number".format(
                        self.url
                    )
                )
                return None

            cd = c["code"]
            name = (  # noqa: 841
                "{0}-{1}".format(prefix, cd)
                if prefix and not cd.startswith(prefix)
                else cd
            )
            c["name"] = self.spec.safe_enum_name(cd)
            c["definition"] = c.get("definition") or c["name"]
            found.append(c)

            # nested concepts?
            if "concept" in c:
                fnd = self.parsed_codes(c["concept"])
                if fnd is None:
                    return None
                found.extend(fnd)
        return found


class FHIRStructureDefinition(object):
    """ One FHIR structure definition. """

    def __init__(self, spec, profile):
        self.is_manual = False
        self.spec = spec
        self.url = None
        self.targetname = None
        self.structure = None
        self.elements = None
        self.main_element = None
        self._class_map = {}
        self.classes = []
        self._did_finalize = False

        if profile is not None:
            self.parse_profile(profile)

    @property
    def name(self):
        return self.structure.name if self.structure is not None else None

    def read_profile(self, filepath):
        """ Read the JSON definition of a profile from disk and parse.

        Not currently used.
        """
        profile = None
        with io.open(filepath, "r", encoding="utf-8") as handle:
            profile = json.load(handle)
        self.parse_profile(profile)

    def parse_profile(self, profile):
        """ Parse a JSON profile into a structure.
        """
        assert profile
        assert "StructureDefinition" == profile["resourceType"]

        # parse structure
        self.url = profile.get("url")
        logger.info('Parsing profile "{0}"'.format(profile.get("name")))
        self.structure = FHIRStructureDefinitionStructure(self, profile)

    def process_profile(self):
        """ Extract all elements and create classes.
        """
        struct = self.structure.differential  # or self.structure.snapshot
        if struct is not None:
            mapped = {}
            self.elements = []
            for elem_dict in struct:
                element = FHIRStructureDefinitionElement(
                    self, elem_dict, self.main_element is None
                )
                self.elements.append(element)
                mapped[element.path] = element

                # establish hierarchy (may move to extra loop in
                # case elements are no longer in order)
                if element.is_main_profile_element:
                    self.main_element = element
                parent = mapped.get(element.parent_name)
                if parent:
                    parent.add_child(element)

            # resolve element dependencies
            for element in self.elements:
                element.resolve_dependencies()

            # run check: if n_min > 0 and parent is in summary, must also be in summary
            for element in self.elements:
                if element.n_min is not None and element.n_min > 0:
                    if (
                        element.parent is not None
                        and element.parent.is_summary
                        and not element.is_summary
                    ):
                        logger.error(
                            "n_min > 0 but not summary: `{0}`".format(element.path)
                        )
                        element.summary_n_min_conflict = True

        # create classes and class properties
        if self.main_element is not None:
            snap_class, subs = self.main_element.create_class()
            if snap_class is None:
                raise Exception(
                    'The main element for "{0}" did not create a class'.format(self.url)
                )

            self.found_class(snap_class)
            for sub in subs:
                self.found_class(sub)
            self.targetname = snap_class.name

    def element_with_id(self, ident):
        """ Returns a FHIRStructureDefinitionElementDefinition with the given
        id, if found. Used to retrieve elements defined via `contentReference`.
        """
        if self.elements is not None:
            for element in self.elements:
                if element.definition.id == ident:
                    return element
        return None

    # MARK: Class Handling
    def found_class(self, klass):
        self.classes.append(klass)

    def needed_external_classes(self):
        """ Returns a unique list of class items that are needed for any of the
        receiver's classes' properties and are not defined in this profile.

        :raises: Will raise if called before `finalize` has been called.
        """
        if not self._did_finalize:
            raise Exception("Cannot use `needed_external_classes` before finalizing")

        internal = set([c.name for c in self.classes])
        needed = set()
        needs = []

        for klass in self.classes:
            # are there superclasses that we need to import?
            sup_cls = klass.superclass
            if (
                sup_cls is not None
                and sup_cls.name not in internal
                and sup_cls.name not in needed
            ):
                needed.add(sup_cls.name)
                needs.append(sup_cls)

            # look at all properties' classes and assign their modules
            for prop in klass.properties:
                prop_cls_name = prop.class_name
                if (
                    prop_cls_name not in internal
                    and not self.spec.class_name_is_native(prop_cls_name)
                ):
                    prop_cls = FHIRClass.with_name(prop_cls_name)
                    if prop_cls is None:
                        raise Exception(
                            'There is no class "{0}" for property '
                            '"{1}" on "{2}" in {3}'.format(
                                prop_cls_name, prop.name, klass.name, self.name
                            )
                        )
                    else:
                        prop.module_name = prop_cls.module
                        if prop_cls_name not in needed:
                            needed.add(prop_cls_name)
                            needs.append(prop_cls)

        return sorted(needs, key=lambda n: n.module or n.name)

    def referenced_classes(self):
        """ Returns a unique list of **external** class names that are
        referenced from at least one of the receiver's `Reference`-type
        properties.

        :raises: Will raise if called before `finalize` has been called.
        """
        if not self._did_finalize:
            raise Exception("Cannot use `referenced_classes` before finalizing")

        references = set()
        for klass in self.classes:
            for prop in klass.properties:
                if len(prop.reference_to_names) > 0:
                    references.update(prop.reference_to_names)

        # no need to list references to our own classes, remove them
        for klass in self.classes:
            references.discard(klass.name)

        return sorted(references)

    def writable_classes(self):
        classes = []
        for klass in self.classes:
            if klass.should_write():
                classes.append(klass)
        return classes

    # MARK: Finalizing
    def finalize(self):
        """ Our spec object calls this when all profiles have been parsed.
        """
        # assign all super-classes as objects
        for cls in self.classes:
            if cls.superclass is None:
                super_cls = FHIRClass.with_name(cls.superclass_name)
                if super_cls is None and cls.superclass_name is not None:
                    raise Exception(
                        "There is no class implementation for class "
                        'named "{0}" in profile "{1}"'.format(
                            cls.superclass_name, self.url
                        )
                    )
                else:
                    cls.superclass = super_cls

        self._did_finalize = True


class FHIRStructureDefinitionStructure(object):
    """ The actual structure of a complete profile.
    """

    def __init__(self, profile, profile_dict):
        self.profile = profile
        self.name = None
        self.base = None
        self.kind = None
        self.subclass_of = None
        self.snapshot = None
        self.differential = None

        self.parse_from(profile_dict)

    def parse_from(self, json_dict):
        name = json_dict.get("name")
        if not name:
            raise Exception("Must find 'name' in profile dictionary but found nothing")
        self.name = self.profile.spec.class_name_for_profile(name)
        self.base = json_dict.get("baseDefinition")
        self.kind = json_dict.get("kind")
        if self.base:
            self.subclass_of = self.profile.spec.class_name_for_profile(self.base)

        # find element definitions
        if "snapshot" in json_dict:
            self.snapshot = json_dict["snapshot"].get("element", [])
        if "differential" in json_dict:
            self.differential = json_dict["differential"].get("element", [])


class FHIRStructureDefinitionElement(object):
    """ An element in a profile's structure.
    """

    def __init__(
        self,
        profile: FHIRStructureDefinition,
        element_dict: dict,
        is_main_profile_element: bool = False,
    ):
        assert isinstance(profile, FHIRStructureDefinition)

        self.profile = profile
        self.path = None
        self.parent = None
        self.children = None
        self.parent_name = None
        self.definition = None
        self.n_min = None
        self.n_max = None
        self.is_summary = False
        self.summary_n_min_conflict = False  # to mark conflicts, see #13215
        # (http://gforge.hl7.org/gf/project/fhir/tracker/?action=TrackerItemEdit&tracker_item_id=13125)
        self.valueset = None
        self.enum = None  # assigned if the element has a binding to a
        # ValueSet that is a CodeSystem generating an enum

        self.is_main_profile_element = is_main_profile_element
        self.represents_class = False

        self._superclass_name = None
        self._did_resolve_dependencies = False

        if element_dict is not None:
            self.parse_from(element_dict)
        else:
            self.definition = FHIRStructureDefinitionElementDefinition(self, None)

    def parse_from(self, element_dict):
        """ """
        self.path = element_dict["path"]
        parts = self.path.split(".")
        self.parent_name = ".".join(parts[:-1]) if len(parts) > 0 else None
        prop_name = parts[-1]
        if "-" in prop_name:
            prop_name = "".join([n[:1].upper() + n[1:] for n in prop_name.split("-")])

        self.definition = FHIRStructureDefinitionElementDefinition(self, element_dict)
        self.definition.prop_name = prop_name

        self.n_min = element_dict.get("min")
        self.n_max = element_dict.get("max")
        self.is_summary = element_dict.get("isSummary")

    def resolve_dependencies(self):
        """ """
        if self.is_main_profile_element:
            self.represents_class = True
        if (
            not self.represents_class
            and self.children is not None
            and len(self.children) > 0
        ):
            self.represents_class = True
        if self.definition is not None:
            self.definition.resolve_dependencies()

        self._did_resolve_dependencies = True

    # MARK: Hierarchy
    def add_child(self, element):
        assert isinstance(element, FHIRStructureDefinitionElement)
        element.parent = self
        if self.children is None:
            self.children = [element]
        else:
            self.children.append(element)

    def create_class(self, module=None):
        """ Creates a FHIRClass instance from the receiver, returning the
        created class as the first and all inline defined subclasses as the
        second item in the tuple.
        """
        assert self._did_resolve_dependencies
        if not self.represents_class:
            return None, None

        class_name = self.name_if_class()  # noqa: F841
        subs = []
        cls, did_create = FHIRClass.for_element(self)
        if did_create:
            logger.debug('Created class "{0}"'.format(cls.name))
            if module is None and self.is_main_profile_element:
                module = self.profile.spec.as_module_name(cls.name)
            cls.module = module

        # child classes
        if self.children is not None:
            for child in self.children:
                properties = child.as_properties()
                if properties is not None:

                    # collect subclasses
                    sub, subsubs = child.create_class(module)
                    if sub is not None:
                        subs.append(sub)
                    if subsubs is not None:
                        subs.extend(subsubs)

                    # add properties to class
                    if did_create:
                        for prop in properties:
                            cls.add_property(prop)

        return cls, subs

    def as_properties(self):
        """ If the element describes a *class property*, returns a list of
        FHIRClassProperty instances, None otherwise.
        """
        assert self._did_resolve_dependencies
        if self.is_main_profile_element or self.definition is None:
            return None

        # TODO: handle slicing information (not sure why these properties were
        # omitted previously)
        # if self.definition.slicing:
        #    logger.debug('Omitting property "{}"
        # for slicing'.format(self.definition.prop_name))
        #    return None

        # this must be a property
        if self.parent is None:
            raise Exception(
                'Element reports as property but has no parent: "{}"'.format(self.path)
            )

        # create a list of FHIRClassProperty instances (usually with only 1 item)
        if len(self.definition.types) > 0:
            props = []
            for type_obj in self.definition.types:

                # an inline class
                if (
                    "BackboneElement" == type_obj.code or "Element" == type_obj.code
                ):  # data types don't use "BackboneElement"
                    props.append(
                        FHIRClassProperty(self, type_obj, self.name_if_class())
                    )
                    # TODO: look at
                    # http://hl7.org/fhir/StructureDefinition/structuredefinition-\
                    # explicit-type-name ?
                else:
                    props.append(FHIRClassProperty(self, type_obj))
            return props

        # no `type` definition in the element:
        # it's a property with an inline class definition
        type_obj = FHIRElementType()
        return [FHIRClassProperty(self, type_obj, self.name_if_class())]

    # MARK: Name Utils
    def name_of_resource(self):
        assert self._did_resolve_dependencies
        if not self.is_main_profile_element:
            return self.name_if_class()
        return self.definition.name or self.path

    def name_if_class(self):
        return self.definition.name_if_class()

    @property
    def superclass_name(self):
        """ Determine the superclass for the element (used for class elements).
        """
        if self._superclass_name is None:
            tps = self.definition.types
            if len(tps) > 1:
                raise Exception(
                    "Have more than one type to "
                    'determine superclass in "{0}": "{1}"'.format(self.path, tps)
                )
            type_code = None

            if (
                self.is_main_profile_element
                and self.profile.structure.subclass_of is not None
            ):
                type_code = self.profile.structure.subclass_of
            elif len(tps) > 0:
                type_code = tps[0].code
            elif self.profile.structure.kind:
                type_code = self.profile.spec.settings.default_base.get(
                    self.profile.structure.kind
                )
            self._superclass_name = self.profile.spec.class_name_for_type(type_code)

        return self._superclass_name


class FHIRStructureDefinitionElementDefinition(object):
    """ The definition of a FHIR element.
    """

    def __init__(self, element, definition_dict):
        self.id = None
        self.element = element
        self.types = []
        self.name = None
        self.prop_name = None
        self.content_reference = None
        self._content_referenced = None
        self.short = None
        self.formal = None
        self.comment = None
        self.binding = None
        self.constraint = None
        self.mapping = None
        self.slicing = None
        self.representation = None
        # TODO: extract "defaultValue[x]", "fixed[x]", "pattern[x]"
        # TODO: handle  "slicing"

        if definition_dict is not None:
            self.parse_from(definition_dict)

    def parse_from(self, definition_dict):
        self.id = definition_dict.get("id")
        self.types = []
        for type_dict in definition_dict.get("type", []):
            self.types.append(FHIRElementType(type_dict))

        self.name = definition_dict.get("name")
        self.content_reference = definition_dict.get("contentReference")

        self.short = definition_dict.get("short")
        self.formal = definition_dict.get("definition")
        if (
            self.formal and self.short == self.formal[:-1]
        ):  # formal adds a trailing period
            self.formal = None
        self.comment = definition_dict.get("comments")

        if "binding" in definition_dict:
            self.binding = FHIRElementBinding(definition_dict["binding"])
        if "constraint" in definition_dict:
            self.constraint = FHIRElementConstraint(definition_dict["constraint"])
        if "mapping" in definition_dict:
            self.mapping = FHIRElementMapping(definition_dict["mapping"])
        if "slicing" in definition_dict:
            self.slicing = definition_dict["slicing"]
        self.representation = definition_dict.get("representation")

    def resolve_dependencies(self):
        # update the definition from a reference, if there is one
        if self.content_reference is not None:
            if "#" != self.content_reference[:1]:
                raise Exception(
                    "Only relative 'contentReference' element "
                    "definitions are supported right now"
                )
            elem = self.element.profile.element_with_id(self.content_reference[1:])
            if elem is None:
                raise Exception(
                    'There is no element definiton with id "{0}", '
                    "as referenced by {1} in {2}".format(
                        self.content_reference, self.path, self.profile.url
                    )
                )
            self._content_referenced = elem.definition

        # resolve bindings
        if (
            self.binding is not None
            and self.binding.is_required
            and (self.binding.uri is not None or self.binding.canonical is not None)
        ):
            uri = self.binding.canonical or self.binding.uri
            if "http://hl7.org/fhir" != uri[:19]:
                logger.debug('Ignoring foreign ValueSet "{}"'.format(uri))
                return

            valueset = self.element.profile.spec.valueset_with_uri(uri)
            if valueset is None:
                logger.error(
                    'There is no ValueSet for required binding "{}" on {} in {}'.format(
                        uri, self.name or self.prop_name, self.element.profile.name
                    )
                )
            else:
                self.element.valueset = valueset
                self.element.enum = valueset.enum

    def name_if_class(self):
        """ Determines the class-name that the element would have if it was
        defining a class. This means it uses "name", if present, and the last
        "path" component otherwise.
        """
        if self._content_referenced is not None:
            return self._content_referenced.name_if_class()

        with_name = self.name or self.prop_name
        parent_name = (
            self.element.parent.name_if_class()
            if self.element.parent is not None
            else None
        )
        classname = self.element.profile.spec.class_name_for_type(
            with_name, parent_name
        )
        if (
            parent_name is not None
            and self.element.profile.spec.settings.backbone_class_adds_parent
        ):
            classname = parent_name + classname
        return classname


class FHIRElementType(object):
    """ Representing a type of an element.
    """

    def __init__(self, type_dict=None):
        self.code = None
        self.profile = None

        if type_dict is not None:
            self.parse_from(type_dict)

    def parse_from(self, type_dict):
        self.code = type_dict.get("code")
        ext_code = type_dict.get("_code")
        if self.code is None and ext_code is not None:
            json_ext = [
                e
                for e in ext_code.get("extension", [])
                if e.get("url")
                == (
                    "http://hl7.org/fhir/StructureDefinition/"
                    "structuredefinition-json-type"
                )
            ]
            if len(json_ext) < 1:
                raise Exception(
                    'Expecting either "code" or "_code" and '
                    f"a JSON type extension, found neither in {type_dict}"
                )
            if len(json_ext) > 1:
                raise Exception(
                    f"Found more than one structure definition JSON type in {type_dict}"
                )
            self.code = json_ext[0].get("valueString")
        if self.code is None:
            raise Exception(f"No JSON type found in {type_dict}")
        if not _is_string(self.code):
            raise Exception(
                "Expecting a string for 'code' definition "
                "of an element type, got {0} as {1}".format(self.code, type(self.code))
            )
        if not isinstance(type_dict.get("targetProfile"), (list,)):
            self.profile = type_dict.get("targetProfile")
            if (
                self.profile is not None
                and not _is_string(self.profile)
                and not isinstance(type_dict.get("targetProfile"), (list,))
            ):  # Added a check to make sure the targetProfile wasn't a list
                raise Exception(
                    "Expecting a string for 'targetProfile' "
                    "definition of an element type, got {0} as {1}".format(
                        self.profile, type(self.profile)
                    )
                )


class FHIRElementBinding(object):
    """ The "binding" element in an element definition
    """

    def __init__(self, binding_obj):
        self.strength = binding_obj.get("strength")
        self.description = binding_obj.get("description")
        self.uri = binding_obj.get("valueSetUri")
        self.canonical = binding_obj.get("valueSetCanonical")
        self.is_required = "required" == self.strength


class FHIRElementConstraint(object):
    """ Constraint on an element.
    """

    def __init__(self, constraint_arr):
        pass


class FHIRElementMapping(object):
    """ Mapping FHIR to other standards.
    """

    def __init__(self, mapping_arr):
        pass


def _is_string(element):
    isstr = isinstance(element, (str, bytes))
    return isstr


class FHIRClass(object):
    """ An element/resource that should become its own class.
    """

    known = {}

    @classmethod
    def for_element(cls, element):
        """ Returns an existing class or creates one for the given element.
        Returns a tuple with the class and a bool indicating creation.
        """
        assert element.represents_class
        class_name = element.name_if_class()
        if class_name in cls.known:
            return cls.known[class_name], False

        klass = cls(element)
        cls.known[class_name] = klass
        return klass, True

    @classmethod
    def with_name(cls, class_name):
        return cls.known.get(class_name)

    def __init__(self, element):
        assert element.represents_class
        self.path = element.path
        self.name = element.name_if_class()
        self.module = None
        self.resource_type = element.name_of_resource()
        self.superclass = None
        self.superclass_name = element.superclass_name
        self.short = element.definition.short
        self.formal = element.definition.formal
        self.properties = []
        self.expanded_nonoptionals = {}

    def add_property(self, prop):
        """ Add a property to the receiver.

        :param FHIRClassProperty prop: A FHIRClassProperty instance
        """
        assert isinstance(prop, FHIRClassProperty)

        # do we already have a property with this name?
        # if we do and it's a specific reference, make it a reference to a
        # generic resource
        for existing in self.properties:
            if existing.name == prop.name:
                if 0 == len(existing.reference_to_names):
                    logger.warning(
                        'Already have property "{0}" on "{1}", '
                        "which is only allowed for references".format(
                            prop.name, self.name
                        )
                    )
                else:
                    existing.reference_to_names.extend(prop.reference_to_names)
                return

        self.properties.append(prop)
        self.properties = sorted(self.properties, key=lambda x: x.name)

        if prop.nonoptional and prop.one_of_many is not None:
            if prop.one_of_many in self.expanded_nonoptionals:
                self.expanded_nonoptionals[prop.one_of_many].append(prop)
            else:
                self.expanded_nonoptionals[prop.one_of_many] = [prop]

    @property
    def nonexpanded_properties(self):
        nonexpanded = []
        included = set()
        for prop in self.properties:
            if prop.one_of_many:
                if prop.one_of_many in included:
                    continue
                included.add(prop.one_of_many)
            nonexpanded.append(prop)
        return nonexpanded

    @property
    def nonexpanded_nonoptionals(self):
        nonexpanded = []
        included = set()
        for prop in self.properties:
            if not prop.nonoptional:
                continue
            if prop.one_of_many:
                if prop.one_of_many in included:
                    continue
                included.add(prop.one_of_many)
            nonexpanded.append(prop)
        return nonexpanded

    def property_for(self, prop_name):
        for prop in self.properties:
            if prop.orig_name == prop_name:
                return prop
        if self.superclass and self != self.superclass:  # Element is its own superclass
            return self.superclass.property_for(prop_name)
        return None

    def should_write(self):
        if self.superclass is not None:
            return True
        return True if len(self.properties) > 0 else False

    @property
    def has_nonoptional(self):
        for prop in self.properties:
            if prop.nonoptional:
                return True
        return False

    @property
    def sorted_nonoptionals(self):
        return sorted(self.expanded_nonoptionals.items())


class FHIRClassProperty(object):
    """ An element describing an instance property.
    """

    def __init__(self, element, type_obj, type_name=None):
        assert (
            element and type_obj
        )  # and must be instances of FHIRStructureDefinitionElement and FHIRElementType
        spec = element.profile.spec

        self.path = element.path
        # assign if this property has been expanded from "property[x]"
        self.one_of_many = None
        if not type_name:
            type_name = type_obj.code
        # original type name
        self.type_name = type_name

        name = element.definition.prop_name
        if "[x]" in name:
            self.one_of_many = name.replace("[x]", "")
            name = name.replace(
                "[x]", "{0}{1}".format(type_name[:1].upper(), type_name[1:])
            )

        self.orig_name = name
        self.name = spec.safe_property_name(name)
        self.parent_name = element.parent_name
        self.class_name = spec.class_name_for_type_if_property(type_name)
        self.enum = element.enum if "code" == type_name else None
        # should only be set if it's an external module (think Python)
        self.module_name = None
        self.json_class = spec.json_class_for_class_name(self.class_name)
        self.is_native = (
            False if self.enum else spec.class_name_is_native(self.class_name)
        )
        self.is_array = True if "*" == element.n_max else False
        self.is_summary = element.is_summary
        self.is_summary_n_min_conflict = element.summary_n_min_conflict
        self.nonoptional = (
            True if element.n_min is not None and 0 != int(element.n_min) else False
        )
        self.reference_to_names = (
            [spec.class_name_for_profile(type_obj.profile)]
            if type_obj.profile is not None
            else []
        )
        self.short = element.definition.short
        self.formal = element.definition.formal
        self.representation = element.definition.representation


class FHIRSearchSpec(object):
    """https://www.hl7.org/fhir/searchparameter-registry.html
    """

    def __init__(self, source, fhir_release, storage):
        """ """
        self._finalized = False
        self.source = source
        self.storage = IStorage(storage)
        self.fhir_release = fhir_release
        self.parameters_def = list()
        self.prepare()

    def prepare(self):
        """ """
        with io.open(str(self.source / self.jsonfilename), "r", encoding="utf-8") as fp:
            string_val = fp.read()
            spec_dict = json.loads(string_val)

        for entry in spec_dict["entry"]:

            self.parameters_def.append(
                SearchParameterDefinition.from_dict(self, entry["resource"])
            )

    def write(self):
        """ """
        storage = self.storage.get(self.fhir_release.value)

        for param_def in self.parameters_def:
            for resource_type in param_def.expression_map:
                if not storage.exists(resource_type):
                    storage.insert(
                        resource_type, ResoureSearchParameterDefinition(resource_type)
                    )
                obj = storage.get(resource_type)
                # add search param code to obj
                setattr(
                    obj,
                    param_def.code,
                    SearchParameter.from_definition(resource_type, param_def),
                )

        self.apply_base_resource_params()

    def apply_base_resource_params(self):
        """ """
        storage = self.storage.get(self.fhir_release.value)
        base_resource_params = storage.get("Resource")

        for resource_type in storage:
            if resource_type in ("Resource", "DomainResource"):
                continue
            storage.get(resource_type) + base_resource_params

    @property
    def jsonfilename(self):
        """ """
        return "search-parameters.json"


class SearchParameterDefinition(object):
    """ """

    __slots__ = (
        "spec",
        "name",
        "code",
        "expression_map",
        "type",
        "modifier",
        "comparator",
        "target",
        "xpath",
        "multiple_or",
        "multiple_and",
    )

    @classmethod
    def from_dict(cls, spec, dict_value):
        """ """
        self = cls()
        self.spec = spec
        self.name = dict_value["name"]
        self.code = dict_value["code"]
        self.type = dict_value["type"]

        # Add conditional None
        self.xpath = dict_value.get("xpath")
        self.modifier = dict_value.get("modifier", None)
        self.comparator = dict_value.get("comparator", None)
        self.target = dict_value.get("target", None)
        self.multiple_or = dict_value.get("multipleOr", None)
        self.multiple_and = dict_value.get("multipleAnd", None)

        # Make expression map combined with base and expression
        self.expression_map = dict()
        if dict_value.get("expression", None) is None:
            for base in dict_value["base"]:
                self.expression_map[base] = None

            return self
        elif len(dict_value["base"]) == 1:
            self.expression_map[dict_value["base"][0]] = dict_value["expression"]

            return self

        for expression in dict_value["expression"].split("|"):
            exp = expression.strip()
            if exp.startswith("("):
                base = exp[1:].split(".")[0]
            else:
                base = exp.split(".")[0]

            assert base in dict_value["base"]
            self.expression_map[base] = exp

        return self


class SearchParameter(object):
    """ """

    __slots__ = (
        "name",
        "code",
        "expression",
        "type",
        "modifier",
        "comparator",
        "target",
        "xpath",
        "multiple_or",
        "multiple_and",
    )

    @classmethod
    def from_definition(cls, resource_type, definition):
        """ """
        self = cls()
        self.name = definition.name
        self.code = definition.code
        self.type = definition.type
        self.xpath = definition.xpath
        self.modifier = definition.modifier
        self.comparator = definition.comparator
        self.target = definition.target
        self.multiple_or = definition.multiple_or
        self.multiple_and = definition.multiple_and
        self.expression = self.get_expression(resource_type, definition)

        return self

    def get_expression(self, resource_type, definition):
        """ """
        exp = definition.expression_map[resource_type]
        if not exp:
            return exp
        # try cleanup Zero Width Space
        if "\u200b" in exp:
            exp = exp.replace("\u200b", "")

        return exp.strip()

    def clone(self):
        """ """
        return self.__copy__()

    def __copy__(self):
        """ """
        newone = type(self).__new__(type(self))
        newone.name = copy(self.name)
        newone.code = copy(self.code)
        newone.type = copy(self.type)
        newone.xpath = copy(self.xpath)
        newone.modifier = copy(self.modifier)
        newone.comparator = copy(self.comparator)
        newone.target = copy(self.target)
        newone.multiple_or = copy(self.multiple_or)
        newone.multiple_and = copy(self.multiple_and)
        newone.expression = copy(self.expression)

        return newone


class ResoureSearchParameterDefinition(object):
    """ """

    __slots__ = ("__storage__", "_finalized", "resource_type")

    def __init__(self, resource_type):
        """ """
        object.__setattr__(self, "__storage__", defaultdict())
        object.__setattr__(self, "_finalized", False)
        object.__setattr__(self, "resource_type", resource_type)

    def __getattr__(self, item):
        """
        :param item:
        :return:
        """
        try:
            return self.__storage__[item]
        except KeyError:
            msg = "Object from {0!s} has no attribute `{1}`".format(
                self.__class__.__name__, item
            )
            reraise(AttributeError, msg)

    def __setattr__(self, name, value):
        """ """
        if self._finalized:
            raise TypeError("Modification of attribute value is not allowed!")

        self.__storage__[name] = value

    def __delattr__(self, item):
        """ """
        if self._finalized:
            raise TypeError("Modification of attribute value is not allowed!")

        try:
            del self.__storage__[item]
        except KeyError:
            msg = "Object from {0!s} has no attribute `{1}`".format(
                self.__class__.__name__, item
            )
            reraise(AttributeError, msg)

    def __add__(self, other):
        """ """
        for key, val in other.__storage__.items():
            copied = val.clone()
            if copied.expression and other.resource_type in copied.expression:
                copied.expression = copied.expression.replace(
                    other.resource_type, self.resource_type
                )

            if copied.xpath and other.resource_type in copied.xpath:
                copied.xpath = copied.xpath.replace(
                    other.resource_type, self.resource_type
                )

            self.__storage__[key] = copied

    def __iter__(self):
        """ """
        for key in self.__storage__:
            yield key

    def __contains__(self, item):
        """ """
        return item in self.__storage__
