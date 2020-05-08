# -*- coding: utf-8 -*-
"""Main module."""
from __future__ import annotations

import inspect
import typing
from functools import wraps

from zope.interface import implementer

from fhirpath.interfaces import ITypeInfoWithElements

from .exceptions import MultipleResultsFound
from .storage import MemoryStorage
from .types import TypeSpecifier


__author__ = "Md Nazrul Islam <email2nazrul>"

FHIR_PREFIX = "FHIR"
FHIRPathType = typing.TypeVar("FHIRPathType", bound="FHIRPath")
FHIRPATH_DATA_TYPES = {
    "bool": "Boolean",
    "str": "String",
    "int": "Integer",
    "float": "Decimal",
    "date": "Date",
    "datetime": "DateTime",
    "time": "Time",
    "bytes": "String",
}


def collection_type_required(func: typing.Callable):
    """ """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not isinstance(self.get_type(), ListTypeInfo):
            raise ValueError(
                f"You are allowed to use this method ´{func.__name__}´, "
                "for collection(list) type value only"
            )
        return func(self, *args, **kwargs)

    return wrapper


class SimpleTypeInfo:
    """For primitive types such as String and Integer,
    the result is a SimpleTypeInfo:"""

    namespace: str
    name: str
    baseType: type

    @classmethod
    def from_type_specifier(cls, specifier):
        """ """
        ns, name = specifier.split(".")
        self = cls()
        self.namespace = ns
        self.name = name
        self.baseType = "{0}<Any>".format(ns)
        return self


class ClassInfoElement:
    name: str
    type: TypeSpecifier
    isOneBased: typing.Optional[bool]
    _common_name: typing.Optional[str]
    _py_class: typing.Any

    def __init__(
        self,
        name: str,
        type_: TypeSpecifier,
        is_one_based: bool = None,
        common_name: str = None,
    ):
        """ """
        self.name = name
        self.type = type_
        self.isOneBased = is_one_based
        self._common_name = common_name

    @classmethod
    def from_el_property_tuple(cls, prop_tuple):
        """("name", "json_name", type, type_name, is_list, "of_many", not_optional)"""
        name = prop_tuple[0]
        is_one_based = prop_tuple[4] is False
        tn = "{0}.{1}".format(FHIR_PREFIX, prop_tuple[3])
        if prop_tuple[4]:
            tn = "List<{0}>".format(tn)
        self = cls(name, TypeSpecifier(tn), is_one_based, prop_tuple[5])
        self._py_class = prop_tuple[2]
        return self


@implementer(ITypeInfoWithElements)
class ClassInfo:
    """ """

    name: str
    namespace: str
    baseType: TypeSpecifier
    element: typing.List[ClassInfoElement]
    _indexes: typing.List[str]

    @classmethod
    def from_object_base(cls, obj, base, elements):
        """ """
        self = cls()
        klass_name = type(obj).__name__
        self.namespace = FHIR_PREFIX
        self.name = klass_name
        self.baseType = "{0}.{1}".format(FHIR_PREFIX, base.__name__)
        self._indexes = list()

        for el in elements:
            self._indexes.append(el.name)
        self.element = elements
        # Ensure base in cache
        base_bases = inspect.getmro(base)
        if (
            "FHIRAbstractBase" in str(base_bases)
            and self.baseType not in FHIRPath.__storage__
            and base.__name__ != "FHIRAbstractBase"
        ):
            base_obj = base()
            base_elements = FHIRPath.build_elements(
                base_obj, base_bases[1], ClassInfoElement
            )
            base_self = ClassInfo.from_object_base(
                base_obj, base_bases[1], base_elements
            )
            FHIRPath.__storage__[self.baseType] = base_self

        return self

    def get_elements(self):
        """ """
        return self.element


@implementer(ITypeInfoWithElements)
class ListTypeInfo:
    """For collection types, the result is a ListTypeInfo:
    ``ListTypeInfo { elementType: TypeSpecifier }``

    For example:
    ``Patient.address.type()``

    Results in:
        ``{ListTypeInfo { elementType: 'FHIR.Address' }}``
    """

    elementType: TypeSpecifier

    @classmethod
    def from_specifier(cls, specifier):
        """ """
        assert "." in specifier, "Must contains with prefix!"
        self = cls()
        self.elementType = specifier
        return self

    def get_elements(self):
        """ """
        return FHIRPath.__storage__[self.elementType].get_elements()


class TupleTypeInfoElement(ClassInfoElement):
    """ """


@implementer(ITypeInfoWithElements)
class TupleTypeInfo:
    """Anonymous types are structured types that have no associated name,
    only the elements of the structure. For example, in FHIR, the Patient.contact
    element has multiple sub-elements, but is not explicitly named.
    For types such as this, the result is a TupleTypeInfo:
    @see http://hl7.org/fhirpath/N1/#anonymous-types"""

    element: typing.List[TupleTypeInfoElement]

    def get_elements(self):
        """ """
        return self.element


class FHIRPath(typing.Generic[FHIRPathType]):
    """http://hl7.org/fhirpath/N1"""

    # Global Cache
    __storage__ = MemoryStorage()

    _obj: typing.Any
    _predecessor: type
    _type_info: typing.Union[TupleTypeInfo, ListTypeInfo, ClassInfo, SimpleTypeInfo]
    _prop_name: str
    _of_many: bool

    __slots__ = ("_obj", "_predecessor", "_type_info", "_prop_name", "_of_many")

    def __init__(self, _obj: typing.Any, predecessor=None):
        """ """
        if predecessor is None and "FHIRAbstractBase" not in str(
            inspect.getmro(type(_obj))
        ):
            raise ValueError(
                "root fhirpath cannot be initialized, "
                "without a object (must be derived from "
                "``fhir.resources::FHIRAbstractBase``)"
            )

        if type(_obj).__name__ == "FHIRDate":
            _obj = _obj.date
        object.__setattr__(self, "_obj", _obj)
        object.__setattr__(self, "_predecessor", predecessor)
        object.__setattr__(self, "_type_info", None)
        object.__setattr__(self, "_prop_name", None)
        object.__setattr__(self, "_of_many", None)

    def __getattr__(self, item):
        """ """
        if item in self.__slots__:
            return object.__getattribute__(self, item)
        if self._obj is None:
            raise AttributeError(f"'NoneType' object/value has no attribute '{item}'")
        try:
            obj = getattr(self._obj, item)
            # another instance of FHIRPath with predecessor's referenced
            return self._create_successor(obj, item)
        except AttributeError:
            # special case for `value` name
            valid = False
            obj = None
            for el in self.get_type().get_elements():
                if el._common_name is not None and el._common_name == item:
                    valid = True
                    value = getattr(self._obj, el.name, None)
                    if value is not None:
                        obj = value
                        break
            if valid is True:
                return self._create_successor(obj, item, of_many=True)
            # Real Error
            raise

    def __setattr__(self, attr, value):
        """ """
        raise AttributeError("Readonly Object!")

    def __call__(self):
        """ """
        return self._obj

    @staticmethod
    def element_from_predecessor(predecessor, prop_name):
        """ """
        if predecessor() is None:
            raise NotImplementedError

        predecessor_type = predecessor.get_type()
        if not ITypeInfoWithElements.providedBy(predecessor_type):
            raise NotImplementedError

        for el in predecessor_type.get_elements():
            if el.name == prop_name:
                return el
            elif el._common_name == prop_name:
                # xxx: extra care required.
                return el

        def _from_base(specifier):
            """ """
            try:
                klass_info = FHIRPath.__storage__[specifier]
            except KeyError:
                return
            for el_ in klass_info.get_elements():
                if el_.name == prop_name:
                    return el_
                elif el_._common_name == prop_name:
                    # xxx: extra care
                    return el_
            return _from_base(klass_info.baseType)

        el = _from_base(predecessor_type.baseType)
        return el

    @staticmethod
    def build_elements(obj, base_type, klass):
        """ """
        if base_type is not object:
            base_properties = [item[0] for item in base_type().elementProperties()]
        else:
            base_properties = []
        elements = list()
        for item in obj.elementProperties():
            if item[0] in base_properties:
                continue
            el = klass.from_el_property_tuple(item)
            elements.append(el)

        return elements

    @staticmethod
    def convert_and_cache_elements(elements):
        """ """
        for el in elements:
            specifier = el.type
            if specifier.startswith("List<"):
                specifier = specifier[5:-1]

            if specifier not in FHIRPath.__storage__:
                FHIRPath.__storage__[specifier] = FHIRPath.build_type_info_from_el(el)

    @staticmethod
    def build_type_info_from_el(element):
        """ """
        bases = inspect.getmro(element._py_class)
        if "FHIRAbstractBase" in str(bases):
            # FHIR type!
            klass_info = FHIRPath.build_fhir_abstract_type_info(
                klass=bases[0], base_klass=bases[1]
            )
        else:
            specifier = element.type
            if specifier.startswith("List<"):
                specifier = specifier[5:-1]
            klass_info = SimpleTypeInfo.from_type_specifier(specifier)
        return klass_info

    @staticmethod
    def build_fhir_abstract_type_info(klass, base_klass, is_one_based=True):
        """ """
        obj = klass()
        key = ".".join([FHIR_PREFIX, klass.__name__])

        if key not in FHIRPath.__storage__:
            mod_base_name = inspect.getmodule(obj).__name__.split(".")[-1]
            if mod_base_name == klass.__name__.lower():
                elements = FHIRPath.build_elements(obj, base_klass, ClassInfoElement)
                klass_info = ClassInfo.from_object_base(obj, base_klass, elements)
            else:
                # TupleType
                elements = FHIRPath.build_elements(
                    obj, base_klass, TupleTypeInfoElement
                )
                klass_info = TupleTypeInfo()
                klass_info.element = elements
            # cache it!
            FHIRPath.convert_and_cache_elements(elements)
            FHIRPath.__storage__[key] = klass_info
        if is_one_based is False:
            return ListTypeInfo.from_specifier(key)
        else:
            return FHIRPath.__storage__[key]

    def _assign_type_info(self):
        """("name", "json_name", type, type_name, is_list, "of_many", not_optional)"""
        element = None
        is_one_based = True

        if self._prop_name and self._predecessor:
            element = FHIRPath.element_from_predecessor(
                self._predecessor, self._prop_name
            )

        if element is not None:
            is_one_based = element.isOneBased

        if self._obj is None:
            if element is not None:
                bases = inspect.getmro(element._py_class)
            else:
                return

        else:
            bases = inspect.getmro(type(self._obj))
            if element is None and isinstance(self._obj, list):
                is_one_based = False

        if "FHIRAbstractBase" in str(bases):
            # FHIR type!
            if self._obj is None:
                klass = bases[0]
            else:
                klass = type(self._obj)
            type_info = FHIRPath.build_fhir_abstract_type_info(
                klass, bases[1], is_one_based
            )
            object.__setattr__(self, "_type_info", type_info)

        elif isinstance(self._obj, list) and self._prop_name and self._predecessor:
            """Do special treatment"""
            specifier = None
            element = None
            for el in self._predecessor.get_type().get_elements():
                if el.name == self._prop_name:
                    specifier = el.type[5:-1]
                    element = el
                    break
            if specifier is None:
                raise NotImplementedError

            if specifier not in FHIRPath.__storage__:
                # cache it, important!
                FHIRPath.__storage__[specifier] = FHIRPath.build_type_info_from_el(
                    element
                )

            type_info = ListTypeInfo()
            type_info.elementType = specifier

            object.__setattr__(self, "_type_info", type_info)
        else:
            if self._predecessor:
                predecessor_type = self._predecessor.get_type()
                type_info = None
                if isinstance(predecessor_type, ListTypeInfo):
                    type_info = FHIRPath.__storage__[predecessor_type.elementType]
                elif self._prop_name:
                    for el in self._predecessor.get_type().get_elements():
                        if el.name == self._prop_name:
                            new_type = el.type
                            if new_type.startswith("List<"):
                                new_type = new_type[5:-1]
                            # check in cache
                            if new_type not in FHIRPath.__storage__:

                                FHIRPath.__storage__[
                                    new_type
                                ] = SimpleTypeInfo.from_type_specifier(new_type)
                            type_info = FHIRPath.__storage__[new_type]
                            break
                if type_info is None:
                    raise NotImplementedError
                object.__setattr__(self, "_type_info", type_info)
            else:
                specifier = "System." + FHIRPATH_DATA_TYPES[bases[0].__name__]
                if specifier not in FHIRPath.__storage__:
                    type_info = SimpleTypeInfo.from_type_specifier(specifier)
                    FHIRPath.__storage__[specifier] = type_info
                object.__setattr__(self, "_type_info", FHIRPath.__storage__[specifier])

    def _create_successor(
        self, _obj, prop_name: str = None, of_many: bool = None
    ) -> FHIRPath:
        """ """
        successor: FHIRPath = FHIRPath(_obj, predecessor=self)
        object.__setattr__(successor, "_prop_name", prop_name)
        object.__setattr__(successor, "_of_many", of_many)
        return successor

    def _clone(self, obj=None):
        """ """
        if obj is None:
            obj = self._obj
        newone = FHIRPath(obj, predecessor=self._predecessor)
        object.__setattr__(newone, "_prop_name", self._prop_name)
        object.__setattr__(newone, "_of_many", self._of_many)
        return newone

    #   5.1. Existence
    @collection_type_required
    def empty(self) -> bool:
        """5.1.1. empty() : Boolean
        Returns true if the input collection is empty ({ }) and false otherwise.
        """
        if self._obj is None:
            return True
        return len(self._obj) == 0

    @collection_type_required
    def exists(self):
        """5.1.2. exists([criteria : expression]) : Boolean
        Returns true if the collection has any elements, and false otherwise.
        This is the opposite of empty(), and as such is a shorthand for empty().not().
        If the input collection is empty ({ }), the result is false.

        The function can also take an optional criteria to be applied to the
        collection prior to the determination of the exists. In this case,
        the function is shorthand for where(criteria).exists().
        """
        raise NotImplementedError

    def all(self):
        """5.1.3. all(criteria : expression) : Boolean
        Returns true if for every element in the input collection,
        criteria evaluates to true. Otherwise, the result is false.
        If the input collection is empty ({ }), the result is true.

        ``generalPractitioner.all($this is Practitioner)``
        """
        raise NotImplementedError

    def allTrue(self):
        """5.1.4. allTrue() : Boolean
        Takes a collection of Boolean values and returns true if
        all the items are true. If any items are false, the result is false.
        If the input is empty ({ }), the result is true.

        The following example returns true if all of the components of the
        Observation have a value greater than 90 mm[Hg]:
        ``Observation.select(component.value > 90 'mm[Hg]').allTrue()``
        """
        raise NotImplementedError

    def anyTrue(self):
        """5.1.5. anyTrue() : Boolean
        Takes a collection of Boolean values and returns true
        if any of the items are true.
        If all the items are false, or if the input is empty ({ }),
        the result is false.

        The following example returns true if any of the components of the Observation
        have a value greater than 90 mm[Hg]:
        ``Observation.select(component.value > 90 'mm[Hg]').anyTrue()``
        """
        raise NotImplementedError

    def allFalse(self):
        """5.1.6. allFalse() : Boolean
        Takes a collection of Boolean values and returns true
        if all the items are false.
        If any items are true, the result is false. If the input is empty ({ }),
        the result is true.

        The following example returns true if none of the components of the Observation
        have a value greater than 90 mm[Hg]:
        ``Observation.select(component.value > 90 'mm[Hg]').allFalse()``
        """
        raise NotImplementedError

    def anyFalse(self):
        """5.1.7. anyFalse() : Boolean
        Takes a collection of Boolean values and returns true
        if any of the items are false.
        If all the items are true, or if the input is empty ({ }), the result is false.

        he following example returns true if any of the components of the Observation
        have a value that is not greater than 90 mm[Hg]:
        ``Observation.select(component.value > 90 'mm[Hg]').anyFalse()``
        """
        raise NotImplementedError

    def subsetOf(self):
        """5.1.8. subsetOf(other : collection) : Boolean
        Returns true if all items in the input collection are members of the
        collection passed as the other argument.
        Membership is determined using the = (Equals) (=) operation.

        Conceptually, this function is evaluated by testing each element in the input
        collection for membership in the other collection, with a default of true.
        This means that if the input collection is empty ({ }), the result is true,
        otherwise if the other collection is empty ({ }), the result is false.

        The following example returns true if the tags defined in any contained
        resource are a subset of the tags defined in the MedicationRequest resource:
        ``MedicationRequest.contained.meta.tag.subsetOf(MedicationRequest.meta.tag)``
        """
        raise NotImplementedError

    def supersetOf(self):
        """5.1.9. supersetOf(other : collection) : Boolean
        Returns true if all items in the collection passed
        as the other argument are members
        of the input collection. Membership is determined using
        the = (Equals) (=) operation.

        Conceptually, this function is evaluated by testing each element
        in the other collection for membership in the input collection,
        with a default of true.
        This means that if the other collection is empty ({ }), the result is true,
        otherwise if the input collection is empty ({ }), the result is false.

        The following example returns true
        if the tags defined in any contained resource are
        a superset of the tags defined in the MedicationRequest resource:
        ``MedicationRequest.contained.meta.tag.supersetOf(MedicationRequest.meta.tag)``
        """
        raise NotImplementedError

    @collection_type_required
    def count(self) -> int:
        """5.1.10. count() : Integer
        Returns the integer count of the number of items in the input collection.
        Returns 0 when the input collection is empty.
        """
        return self._obj is not None and len(self._obj) or 0

    def distinct(self):
        """5.1.11. distinct() : collection
        Returns a collection containing only the unique items in the input collection.
        To determine whether two items are the same,
        the = (Equals) (=) operator is used, as defined below.

        If the input collection is empty ({ }), the result is empty.

        Note that the order of elements in the input collection is not
        guaranteed to be preserved in the result.

        The following example returns the distinct list of tags on the given Patient:
        ``Patient.meta.tag.distinct()``
        """
        raise NotImplementedError

    def isDistinct(self):
        """5.1.12. isDistinct() : Boolean
        Returns true if all the items in the input collection are distinct.
        To determine whether two items are distinct,
        the = (Equals) (=) operator is used, as defined below.

        Conceptually, this function is shorthand for a comparison of the count() of
        the input collection against the count() of the distinct()
        of the input collection:
        ``X.count() = X.distinct().count()``
        This means that if the input collection is empty ({ }), the result is true.
        """
        raise NotImplementedError

    #   5.2.Filtering and projection
    def where(self):
        """5.2.1. where(criteria : expression) : collection
        Returns a collection containing only those elements in the input collection
        for which the stated criteria expression evaluates to true. Elements for which
        the expression evaluates to false or empty ({ }) are not included in the result

        If the input collection is empty ({ }), the result is empty.
        If the result of evaluating the condition is other than a single boolean value,
        the evaluation will end and signal an error to the calling environment,
        consistent with singleton evaluation of collections behavior.

        The following example returns the list of telecom elements that have a use
        element with the value of 'official':
        ``Patient.telecom.where(use = 'official')``
        """
        raise NotImplementedError

    def select(self):
        """5.2.2. select(projection: expression) : collection
        Evaluates the projection expression for each item in the input collection.
        The result of each evaluation is added to the output collection.
        If the evaluation results in a collection with multiple items,
        all items are added to the output collection
        (collections resulting from evaluation of projection are flattened).
        This means that if the evaluation for an element results in
        the empty collection ({ }), no element is added to the result,
        and that if the input collection is empty ({ }), the result is empty as well.
        ``Bundle.entry.select(resource as Patient)``

        This example results in a collection with only
        the patient resources from the bundle.
        ``Bundle.entry.select((resource as Patient).telecom.where(system = 'phone'))``

        This example results in a collection with all the telecom
        elements with system of phone for all the patients in the bundle.
        ``Patient.name.where(use = 'usual').select(given.first() + ' ' + family)``
        This example returns a collection containing,
        for each "usual" name for the Patient,
        the concatenation of the first given and family names.
        """
        raise NotImplementedError

    def repeat(self):
        """5.2.3. repeat(projection: expression) : collection
        A version of select that will repeat the projection and add it to
        the output collection, as long as the
        projection yields new items (as determined by the = (Equals) (=) operator).

        This function can be used to traverse
        a tree and selecting only specific children:
        ``ValueSet.expansion.repeat(contains)``

        Will repeat finding children called contains, until no new nodes are found.
        ``Questionnaire.repeat(item)``

        Will repeat finding children called item, until no new nodes are found.
        Note that this is slightly different from:
        ``Questionnaire.descendants().select(item)``

        which would find any descendants called item, not just the
        ones nested inside other item elements.
        The order of items returned by the repeat() function is undefined.
        """
        raise NotImplementedError

    def ofType(self, type_cls: typing.Union[type, str]):
        """5.2.4. ofType(type : type specifier) : collection
        Returns a collection that contains all items in
        the input collection that are of the given type or a subclass thereof.
        If the input collection is empty ({ }), the result is empty.
        The type argument is an identifier that must resolve to
        the name of a type in a model. For implementations with compile-time typing,
        this requires special-case handling when processing the argument to treat it as
        type specifier rather than an identifier expression:
        ``Bundle.entry.resource.ofType(Patient)``

        In the above example, the symbol Patient must be treated as a type
        identifier rather than a reference to a Patient in context.
        """
        raise NotImplementedError

    #   5.3. Subsetting
    def __getitem__(self, key: typing.Union[int, slice]):
        """5.3.1. [ index : Integer ] : collection
        The indexer operation returns a collection with only the index-th item
        (0-based index). If the input collection is empty ({ }),
        or the index lies outside the boundaries of the input collection,
        an empty collection is returned.

        ``Note: Unless specified otherwise by the underlying Object Model,
        the first item in a collection has index 0.Note that if the underlying
        model specifies that a collection is 1-based (the only reasonable alternative
        to 0-based collections), any collections generated from operations on
        the 1-based list are 0-based.``

        The following example returns the element in the name collection
        of the Patient with index 0:
        ``Patient.name[0]``
        """
        if not isinstance(self.get_type(), ListTypeInfo):
            raise NotImplementedError("Must be collection")
        try:
            if isinstance(key, slice):
                print(key.start, key.stop)
                obj = self._obj[key.start : key.stop]
                if len(obj) == 0:
                    return
                return self._clone(obj)
            else:
                obj = self._obj[key]
                return self._create_successor(obj)

        except IndexError:
            pass

    @collection_type_required
    def single(self):
        """5.3.2. single() : collection
        Will return the single item in the input if there is just one item.
        If the input collection is empty ({ }), the result is empty.
        If there are multiple items, an error is signaled
        to the evaluation environment.
        This function is useful for ensuring that an error is returned if an assumption
        about cardinality is violated at run-time.

        The following example returns the name of the Patient if there is one.
        If there are no names, an empty collection, and if there are multiple names,
        an error is signaled to the evaluation environment:
        ``Patient.name.single()``
        """
        if self._obj is None or (isinstance(self._obj, list) and len(self._obj) == 0):
            return None
        if len(self._obj) == 1:
            return self[0]

        raise MultipleResultsFound

    @collection_type_required
    def first(self):
        """5.3.3. first() : collection
        Returns a collection containing only the first item in the input collection.
        This function is equivalent to item[0], so it will return an empty collection
        if the input collection has no items.
        """
        if self._obj is None or (isinstance(self._obj, list) and len(self._obj) == 0):
            return None
        return self[0]

    @collection_type_required
    def last(self):
        """5.3.4. last() : collection
        Returns a collection containing only the last item in the input collection.
        Will return an empty collection if the input collection has no items.
        """
        if self._obj is None or (isinstance(self._obj, list) and len(self._obj) == 0):
            return None
        return self[-1]

    @collection_type_required
    def tail(self):
        """5.3.5. tail() : collection
        Returns a collection containing all but the first item in the input collection.
        Will return an empty collection if the input collection has no items,
        or only one item.
        """
        if self._obj is None or (isinstance(self._obj, list) and len(self._obj) < 2):
            return None
        return self[1:]

    @collection_type_required
    def skip(self, num: int):
        """5.3.6. skip(num : Integer) : collection
        Returns a collection containing all but the first num items
        in the input collection.
        Will return an empty collection if there are no items remaining after the
        indicated number of items have been skipped,
        or if the input collection is empty.
        If num is less than or equal to zero, the input collection is simply returned.
        """
        raise NotImplementedError

    @collection_type_required
    def take(self, num: int):
        """5.3.7. take(num : Integer) : collection
        Returns a collection containing the first num items in the input collection,
        or less if there are less than num items. If num is less than or equal to 0,
        or if the input collection is empty ({ }), take returns an empty collection.
        """
        raise NotImplementedError

    def intersect(self):
        """5.3.8. intersect(other: collection) : collection
        Returns the set of elements that are in both collections.
        Duplicate items will be eliminated by this function.
        Order of items is not guaranteed to be preserved
        in the result of this function.
        """
        raise NotImplementedError

    def exclude(self):
        """5.3.9. exclude(other: collection) : collection
        Returns the set of elements that are not in the other collection.
        Duplicate items will not be eliminated by this function,
        and order will be preserved.
        e.g. ``(1 | 2 | 3).exclude(2) returns (1 | 3)``.
        """
        raise NotImplementedError

    #   5.4. Combining
    def union(self):
        """5.4.1. union(other : collection)
        Merge the two collections into a single collection,
        eliminating any duplicate values (using = (Equals) (=) to determine equality).
        There is no expectation of order in the resulting collection.

        In other words, this function returns the distinct list of
        elements from both inputs.
        For example, consider two lists of integers A: 1, 1, 2, 3 and B: 2, 3:
        ``A union B // 1, 2, 3``
        ``A union { } // 1, 2, 3``

        This function can also be invoked using the | operator.
        ``a.union(b)``
        is synonymous with
        ``a | b``
        """
        raise NotImplementedError

    def combine(self):
        """5.4.2. combine(other : collection) : collection
        Merge the input and other collections into a single collection without
        eliminating duplicate values.
        Combining an empty collection with a non-empty collection will return
        the non-empty collection.
        There is no expectation of order in the resulting collection.
        """
        raise NotImplementedError

    #   5.5. Conversion
    def iif(self):
        """5.5.1. iif(criterion: expression, true-result: collection [,
        otherwise-result: collection]) : collection

        The iif function in FHIRPath is an immediate if,
        also known as a conditional operator (such as C’s ? : operator).
        The criterion expression is expected to evaluate to a Boolean.
        If criterion is true, the function returns
        the value of the true-result argument.

        If criterion is false or an empty collection,
        the function returns otherwise-result,
        unless the optional otherwise-result is not given,
        in which case the function returns an empty collection.

        Note that short-circuit behavior is expected in this function.
        In other words, true-result should only be evaluated
        if the criterion evaluates to true, and
        otherwise-result should only be evaluated otherwise.
        For implementations, this means delaying evaluation of the arguments.
        """
        raise NotImplementedError

    #   5.5.2. Boolean Conversion Functions
    def toBoolean(self):
        """5.5.2 toBoolean() : Boolean
        If the input collection contains a single item, this function will return a
        single boolean if:

        - the item is a Boolean
        - the item is an Integer and is equal to one of the possible integer
          representations of Boolean values
        - the item is a Decimal that is equal to one of the possible decimal
          representations of Boolean values
        - the item is a String that is equal to one of the possible string
          representations of Boolean values

        If the item is not one the above types, or the item is a String, Integer,
        or Decimal, but is not equal to one of the possible
        values convertible to a Boolean, the result is empty.
        @see: https://www.hl7.org/fhirpath/#boolean-conversion-functions
        """
        raise NotImplementedError

    def convertsToBoolean(self):
        """5.5.2. convertsToBoolean() : Boolean
        If the input collection contains a single item,
        this function will return true if:

        - the item is a Boolean
        - the item is an Integer that is equal to one of the possible
          integer representations of Boolean values
        - the item is a Decimal that is equal to one of the possible decimal
          representations of Boolean values
        - the item is a String that is equal to one of the possible string
          representations of Boolean values

        If the item is not one of the above types, or the item is a String,
        Integer, or Decimal, but is not equal to one of the possible values
        convertible to a Boolean, the result is false.

        Possible values for Integer, Decimal,
        and String are described in the toBoolean() function.

        If the input collection contains multiple items,
        the evaluation of the expression will end and signal an error
        to the calling environment.

        If the input collection is empty, the result is empty.
        """
        raise NotImplementedError

    #   5.5.3. Integer Conversion Functions
    def toInteger(self):
        """5.5.3 toInteger() : Integer
        If the input collection contains a single item,
        this function will return a single integer if:

        - the item is an Integer
        - the item is a String and is convertible to an integer
        - the item is a Boolean, where true results in a 1 and false results in a 0.

        If the item is not one the above types, the result is empty.

        If the item is a String, but the string is not convertible to an integer
        (using the regex format ``(\\+|-)?\\d+)``, the result is empty.
        If the input collection contains multiple items, the evaluation of the
        expression will end and signal an error to the calling environment.
        If the input collection is empty, the result is empty.
        """
        raise NotImplementedError

    def convertsToInteger(self):
        """5.5.3 convertsToInteger() : Boolean
        If the input collection contains a single item,
        this function will return true if:

        - the item is an Integer
        - the item is a String and is convertible to an Integer
        - the item is a Boolean

        If the item is not one of the above types, or the item is a String,
        but is not convertible to an Integer (using the regex format (\\+|-)?\\d+),
        the result is false.

        If the input collection contains multiple items, the evaluation
        of the expression will end and signal an error to the calling environment.

        If the input collection is empty, the result is empty.
        """
        raise NotImplementedError

    #   5.5.4. Date Conversion Functions
    def toDate(self):
        """5.5.4 toDate() : Date
        If the input collection contains a single item,
        this function will return a single date if:

        - the item is a Date
        - the item is a DateTime
        - the item is a String and is convertible to a Date

        If the item is not one of the above types, the result is empty.

        If the item is a String, but the string is not convertible to a
        Date (using the format YYYY-MM-DD), the result is empty.

        If the input collection contains multiple items, the evaluation
        of the expression will end and signal an error to the calling environment.

        If the input collection is empty, the result is empty.
        """
        raise NotImplementedError

    def convertsToDate(self):
        """5.5.4. convertsToDate() : Boolean
        If the input collection contains a single item,
        this function will return true if:

        - the item is a Date
        - the item is a DateTime
        - the item is a String and is convertible to a Date

        If the item is not one of the above types, or is not convertible to a Date
        (using the format YYYY-MM-DD), the result is false.

        If the item contains a partial date (e.g. '2012-01'),
        the result is a partial date.

        If the input collection contains multiple items, the evaluation of the
        expression will end and signal an error to the calling environment.

        If the input collection is empty, the result is empty.
        """
        raise NotImplementedError

    #   5.5.5. DateTime Conversion Functions
    def toDateTime(self):
        """5.5.5 toDateTime() : DateTime
        If the input collection contains a single item, this function will return a
        single datetime if:

        - the item is a DateTime
        - the item is a Date, in which case the result is a DateTime with the year,
          month, and day of the Date, and the time components empty (not set to zero)
        - the item is a String and is convertible to a DateTime

        If the item is not one of the above types, the result is empty.
        If the item is a String, but the string is not convertible to a
        DateTime (using the format YYYY-MM-DDThh:mm:ss.fff(+|-)hh:mm),
        the result is empty.

        If the item contains a partial datetime (e.g. '2012-01-01T10:00'),
        the result is a partial datetime.

        If the input collection contains multiple items, the evaluation of the
        expression will end and signal an error to the calling environment.

        If the input collection is empty, the result is empty.
        """
        raise NotImplementedError

    def convertsToDateTime(self):
        """5.5.5. convertsToDateTime() : Boolean
        If the input collection contains a single item,
        this function will return true if:

        - the item is a DateTime
        - the item is a Date
        - the item is a String and is convertible to a DateTime

        If the item is not one of the above types, or is not convertible to a DateTime
        (using the format YYYY-MM-DDThh:mm:ss.fff(+|-)hh:mm), the result is false.

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.

        If the input collection is empty, the result is empty.
        """
        raise NotImplementedError

    #   5.5.6. Decimal Conversion Functions
    def toDecimal(self):
        """5.5.6. toDecimal() : Decimal
        If the input collection contains a single item, this function will return
        a single decimal if:

        - the item is an Integer or Decimal
        - the item is a String and is convertible to a Decimal
        - the item is a Boolean, where true results in a 1.0
          and false results in a 0.0.

        If the item is not one of the above types, the result is empty.

        If the item is a String, but the string is not convertible to a Decimal
        (using the regex format (\\+|-)?\\d+(\\.\\d+)?), the result is empty.

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.

        If the input collection is empty, the result is empty.
        """
        raise NotImplementedError

    def convertsToDecimal(self):
        """5.5.6. convertsToDecimal() : Boolean
        If the input collection contains a single item, this function will true if:

        - the item is an Integer or Decimal
        - the item is a String and is convertible to a Decimal
        - the item is a Boolean

        If the item is not one of the above types, or is not convertible to a Decimal
        (using the regex format (\\+|-)?\\d+(\\.\\d+)?), the result is false.

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.

        If the input collection is empty, the result is empty.
        """
        raise NotImplementedError

    #   5.5.7. Quantity Conversion Functions

    def toQuantity(self):
        """5.5.7. toQuantity([unit : String]) : Quantity
        If the input collection contains a single item,
        this function will return a single quantity if:

        - the item is an Integer, or Decimal, where the resulting quantity will
          have the default unit ('1')
        - the item is a Quantity
        - the item is a String and is convertible to a Quantity
        - the item is a Boolean, where true results in the quantity 1.0 '1',
          and false results in the quantity 0.0 '1'

        If the item is not one of the above types, the result is empty.
        If the item is a String, but the string is not convertible

        to a Quantity using the following regex format:
        ``(?'value'(\\+|-)?\\d+(\\.\\d+)?)\\s*('(?'unit'[^']+)'|(?'time'[a-zA-Z]+))?``
        then the result is empty. For example,
        the following are valid quantity strings: ``'4 days'`` ``'10 \'mg[Hg]\''``

        If the input collection contains multiple items,
        the evaluation of the expression will end and signal
        an error to the calling environment.

        If the input collection is empty, the result is empty.
        @see https://www.hl7.org/fhirpath/#toquantityunit-string-quantity
        """
        raise NotImplementedError

    def convertsToQuantity(self):
        """5.5.7. convertsToQuantity([unit : String]) : Boolean
        If the input collection contains a single item,
        this function will return true if:

        - the item is an Integer, Decimal, or Quantity
        - the item is a String that is convertible to a Quantity
        - the item is a Boolean

        If the item is not one of the above types, or is not convertible
        to a Quantity using the following regex format:
        ``(?'value'(\\+|-)?\\d+(\\.\\d+)?)\\s*('(?'unit'[^']+)'|(?'time'[a-zA-Z]+))?``
        then the result is false.

        If the input collection contains multiple items,
        the evaluation of the expression will end and signal an
        error to the calling environment.

        If the input collection is empty, the result is empty.
        @see https://www.hl7.org/fhirpath/#convertstoquantityunit-string-boolean
        """
        raise NotImplementedError

    #   5.5.8. String Conversion Functions
    def toString(self):
        """5.5.8. toString() : String
        If the input collection contains a single item, this function will
        return a single String if:

        - the item in the input collection is a String
        - the item in the input collection is an Integer,
          Decimal, Date, Time, DateTime, or Quantity the output will
          contain its String representation
        - the item is a Boolean, where true results in 'true' and false in 'false'.

        If the item is not one of the above types, the result is false.
        @see https://www.hl7.org/fhirpath/#tostring-string
        """
        raise NotImplementedError

    def convertsToString(self):
        """5.5.8. convertsToString() : String
        If the input collection contains a single item,
        this function will return true if:

        - the item is a String
        - the item is an Integer, Decimal, Date, Time, or DateTime
        - the item is a Boolean
        - the item is a Quantity

        If the item is not one of the above types, the result is false.

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.

        If the input collection is empty, the result is empty.
        """
        raise NotImplementedError

    #   5.5.9. Time Conversion Functions
    def toTime(self):
        """5.5.9. toTime() : Time
        If the input collection contains a single item,
        this function will return a single time if:

        - the item is a Time
        - the item is a String and is convertible to a Time

        If the item is not one of the above types, the result is empty.

        If the item is a String, but the string is not convertible to a Time
        (using the format hh:mm:ss.fff(+|-)hh:mm), the result is empty.

        If the item contains a partial time (e.g. '10:00'),
        the result is a partial time.

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.

        If the input collection is empty, the result is empty.
        """
        raise NotImplementedError

    def convertsToTime(self):
        """5.5.9 convertsToTime() : Boolean
        If the input collection contains a single item,
        this function will return true if:

        - the item is a Time
        - the item is a String and is convertible to a Time

        If the item is not one of the above types, or is not convertible to a
        Time (using the format hh:mm:ss.fff(+|-)hh:mm), the result is false.

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.

        If the input collection is empty, the result is empty.
        """
        raise NotImplementedError

    # 5.6. String Manipulation

    def indexOf(self):
        """5.6.1. indexOf(substring : String) : Integer
        Returns the 0-based index of the first position substring is found in the
        input string, or -1 if it is not found.

        If substring is an empty string (''), the function returns 0.

        If the input or substring is empty ({ }), the result is empty ({ }).

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.
        ```
        'abcdefg'.indexOf('bc') // 1
        'abcdefg'.indexOf('x') // -1
        'abcdefg'.indexOf('abcdefg') // 0
        ```
        """
        raise NotImplementedError

    def substring(self):
        """5.6.2. substring(start : Integer [, length : Integer]) : String
        Returns the part of the string starting at position start (zero-based).
        If length is given, will return at most length number of characters
        from the input string.

        If start lies outside the length of the string,
        the function returns empty ({ }). If there are less remaining characters in the
        string than indicated by length, the function returns just
        the remaining characters.

        If the input or start is empty, the result is empty.

        If an empty length is provided, the behavior is the same as
        if length had not been provided.

        If the input collection contains multiple items, the evaluation of the
        expression will end and signal an error to the calling environment.

        ``
        'abcdefg'.substring(3) // 'defg'
        'abcdefg'.substring(1, 2) // 'bc'
        'abcdefg'.substring(6, 2) // 'g'
        'abcdefg'.substring(7, 1) // { }
        ``
        """
        raise NotImplementedError

    def startsWith(self):
        """5.6.3. startsWith(prefix : String) : Boolean
        Returns true when the input string starts with the given prefix.

        If prefix is the empty string (''), the result is true.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.

        ``
        'abcdefg'.startsWith('abc') // true
        'abcdefg'.startsWith('xyz') // false
        ``
        """
        raise NotImplementedError

    def endsWith(self):
        """5.6.4. endsWith(suffix : String) : Boolean
        Returns true when the input string ends with the given suffix.

        If suffix is the empty string (''), the result is true.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation of the
        expression will end and signal an error to the calling environment.

        ``
        'abcdefg'.endsWith('efg') // true
        'abcdefg'.ednsWith('abc') // false
        ``
        """
        raise NotImplementedError

    def contains(self):
        """5.6.5. contains(substring : String) : Boolean
        Returns true when the given substring is a substring of the input string.

        If substring is the empty string (''), the result is true.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.

        ``
        'abc'.contains('b') // true
        'abc'.contains('bc') // true
        'abc'.contains('d') // false
        ``

        ``
        Note: The .contains() function described here is a string function that looks
        for a substring in a string. This is different than the contains operator,
        which is a list operator that looks for an element in a list.
        ``
        """
        raise NotImplementedError

    def upper(self):
        """5.6.6. upper() : String
        Returns the input string with all characters converted to upper case.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.

        ``
        'abcdefg'.upper() // 'ABCDEFG'
        'AbCdefg'.upper() // 'ABCDEFG'
        ``
        """
        raise NotImplementedError

    def lower(self):
        """5.6.7. lower() : String
        Returns the input string with all characters converted to lower case.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation of the
        expression will end and signal an error to the calling environment.

        ``
        'ABCDEFG'.lower() // 'abcdefg'
        'aBcDEFG'.lower() // 'abcdefg'
        ``
        """
        raise NotImplementedError

    def replace(self):
        """5.6.8. replace(pattern : String, substitution : String) : String
        Returns the input string with all instances of pattern replaced
        with substitution. If the substitution is the empty string (''),
        instances of pattern are removed from the result.
        If pattern is the empty string (''), every character in the input
        string is surrounded by the substitution,
        e.g. 'abc'.replace('','x') becomes 'xaxbxcx'.

        If the input collection, pattern, or substitution are empty,
        the result is empty ({ }).

        If the input collection contains multiple items, the evaluation of the
        expression will end and signal an error to the calling environment.

        ``
        'abcdefg'.replace('cde', '123') // 'ab123fg'
        'abcdefg'.replace('cde', '') // 'abfg'
        'abc'.replace('', 'x') // 'xaxbxcx'
        ``
        """
        raise NotImplementedError

    def matches(self):
        """5.6.9. matches(regex : String) : Boolean
        Returns true when the value matches the given regular expression.
        Regular expressions should function consistently, regardless of any
        culture- and locale-specific settings in the environment,
        should be case-sensitive, use 'single line' mode and allow Unicode characters.

        If the input collection or regex are empty, the result is empty ({ }).

        If the input collection contains multiple items, the evaluation of the
        expression will end and signal an error to the calling environment.
        """
        raise NotImplementedError

    def replaceMatches(self):
        """5.6.10. replaceMatches(regex : String, substitution: String) : String
        Matches the input using the regular expression in regex and replaces each
        match with the substitution string. The substitution may refer to identified
        match groups in the regular expression.

        If the input collection, regex, or substitution are empty,
        the result is empty ({ }).

        If the input collection contains multiple items, the evaluation
        of the expression will end and signal an error to the calling environment.

        This example of replaceMatches() will convert a string with a date
        formatted as MM/dd/yy to dd-MM-yy::

            '11/30/1972'.replace('\\b(?<month>\\d{1,2})/
            (?<day>\\d{1,2})/(?<year>\\d{2,4})\\b', '${day}-${month}-${year}')


       ``
       Note: Platforms will typically use native regular expression implementations.
       These are typically fairly similar, but there will always be small differences.
       As such, FHIRPath does not prescribe a particular dialect, but recommends the
       use of the [PCRE] flavor as the dialect most likely to be broadly supported
       and understood.``
        """
        raise NotImplementedError

    def length(self):
        """5.6.11. length() : Integer
        Returns the length of the input string. If the input collection is empty ({ }),
        the result is empty.
        """
        raise NotImplementedError

    def toChars(self):
        """5.6.12. toChars() : collection
        Returns the list of characters in the input string.
        If the input collection is empty ({ }), the result is empty.
        ``
        'abc'.toChars() // { 'a', 'b', 'c' }
        ``
        """
        raise NotImplementedError

    #   5.7.Math
    def abs(self):
        """5.7.1. abs() : Integer | Decimal | Quantity
        Returns the absolute value of the input. When taking the absolute value
        of a quantity, the unit is unchanged.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.

        ``
        (-5).abs() // 5
        (-5.5).abs() // 5.5
        (-5.5 'mg').abs() // 5.5 'mg'
        ``
        """
        raise NotImplementedError

    def ceiling(self):
        """5.7.2. ceiling() : Integer
        Returns the first integer greater than or equal to the input.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation of the
        expression will end and signal an error to the calling environment.

        ``
        1.ceiling() // 1
        1.1.ceiling() // 2
        (-1.1).ceiling() // -1
        ``
        """
        raise NotImplementedError

    def exp(self):
        """5.7.3. exp() : Decimal
        Returns e raised to the power of the input.

        If the input collection contains an Integer, it will be implicitly converted
        to a Decimal and the result will be a Decimal.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation
        of the expression will end and signal an error to the calling environment.

        ``
        0.exp() // 1.0
        (-0.0).exp() // 1.0
        ``
        """
        raise NotImplementedError

    def floor(self):
        """5.7.4. floor() : Integer
        Returns the first integer less than or equal to the input.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation of the
        expression will end and signal an error to the calling environment.

        ``
        1.floor() // 1
        2.1.floor() // 2
        (-2.1).floor() // -3
        ``
        """
        raise NotImplementedError

    def ln(self):
        """5.7.5. ln() : Decimal
        Returns the natural logarithm of the input (i.e. the logarithm base e).

        When used with an Integer, it will be implicitly converted to a Decimal.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation
        of the expression will end and signal an error to the calling environment.
        ``
        1.ln() // 0.0
        1.0.ln() // 0.0
        ``
        """
        raise NotImplementedError

    def log(self):
        """5.7.6. log(base : Decimal) : Decimal
        Returns the logarithm base base of the input number.

        When used with Integers, the arguments will be implicitly
        converted to Decimal.

        If base is empty, the result is empty.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.

        ``
        16.log(2) // 4.0
        100.0.log(10.0) // 2.0
        ``
        """
        raise NotImplementedError

    def power(self):
        """5.7.7. power(exponent : Integer | Decimal) : Integer | Decimal
        Raises a number to the exponent power. If this function is used with Integers,
        the result is an Integer. If the function is used with Decimals, the result
        is a Decimal. If the function is used with a mixture of Integer and Decimal,
        the Integer is implicitly converted to a Decimal and the result is a Decimal.

        If the power cannot be represented (such as the -1 raised to the 0.5),
        the result is empty.

        If the input is empty, or exponent is empty, the result is empty.

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.

        ``
        2.power(3) // 8
        2.5.power(2) // 6.25
        (-1).power(0.5) // empty ({ })
        ``
        """
        raise NotImplementedError

    def round(self):
        """5.7.8. round([precision : Integer]) : Decimal
        Rounds the decimal to the nearest whole number using a traditional
        round (i.e. 0.5 or higher will round to 1). If specified, the precision
        argument determines the decimal place at which the rounding will occur.
        If not specified, the rounding will default to 0 decimal places.

        If specified, the number of digits of precision must be >= 0 or the
        evaluation will end and signal an error to the calling environment.

        If the input collection contains a single item of type Integer,
        it will be implicitly converted to a Decimal.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation of the
        expression will end and signal an error to the calling environment.

        ``
        1.round() // 1
        3.14159.round(3) // 3.142
        ``
        """
        raise NotImplementedError

    def sqrt(self):
        """5.7.9. sqrt() : Decimal
        Returns the square root of the input number as a Decimal.

        If the square root cannot be represented (such as the square root of -1),
        the result is empty.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation of the
        expression will end and signal an error to the calling environment.

        Note that this function is equivalent to raising a number of the power
        of 0.5 using the power() function.

        ``
        81.sqrt() // 9.0
        (-1).sqrt() // empty
        ``
        """
        raise NotImplementedError

    def truncate(self):
        """5.7.10. truncate() : Integer
        Returns the integer portion of the input.

        If the input collection is empty, the result is empty.

        If the input collection contains multiple items, the evaluation of
        the expression will end and signal an error to the calling environment.

        ``
        101.truncate() // 101
        1.00000001.truncate() // 1
        (-1.56).truncate() // -1
        ``
        """
        raise NotImplementedError

    #   5.8. Tree navigation
    def children(self):
        """5.8.1. children() : collection
        Returns a collection with all immediate child nodes of all items in the
        input collection. Note that the ordering of the children is undefined and
        using functions like first() on the result may return different results on
        different platforms.
        """
        raise NotImplementedError

    def descendants(self):
        """5.8.2. descendants() : collection
        Returns a collection with all descendant nodes of all items in
        the input collection.
        The result does not include the nodes in the input collection themselves.
        This function is a shorthand for repeat(children()).
        Note that the ordering of the children is undefined and using
        functions like first() on the result may return different results
        on different platforms.

        note``
        Note: Many of these functions will result in a set of nodes of
        different underlying types.
        It may be necessary to use ofType() as described in the previous section to
        maintain type safety. See Type safety and strict evaluation for
        more information about type safe use of FHIRPath expressions.
        ``
        """
        raise NotImplementedError

    #   5.9. Utility functions
    def trace(self):
        """5.9.1. trace(name : String [, projection: Expression]) : collection
        Adds a String representation of the input collection to the diagnostic log,
        using the name argument as the name in the log. This log should be made
        available to the user in some appropriate fashion. Does not change the input,
        so returns the input collection as output.

        If the projection argument is used, the trace would log the
        result of evaluating the project expression on the input,
        but still return the input to the trace function unchanged.

        ``contained.where(criteria).trace('unmatched', id).empty()``
        The above example traces only the id elements of the result of the where.
        """
        raise NotImplementedError

    #   5.9.2. Current date and time functions
    #   @see https://www.hl7.org/fhirpath/#current-date-and-time-functions
    def now(self):
        """now() : DateTime
        Returns the current date and time, including timezone offset.
        """
        raise NotImplementedError

    def timeOfDay(self):
        """timeOfDay() : Time
        Returns the current time.
        """
        raise NotImplementedError

    def today(self):
        """today() : Date
        Returns the current date.
        """
        raise NotImplementedError

    #   6. Operations
    #   Coming soon
    #   -------------

    #   6.3. Types

    def is_(self, type_cls: typing.Union[type, str]):
        """6.3.2. is(type : type specifier)
        The is() function is supported for backwards compatibility with previous
        implementations of FHIRPath. Just as with the is keyword, the type argument
        is an identifier that must resolve to the name of a type in a model.
        For implementations with compile-time typing, this requires special-case
        handling when processing the argument to treat it as a type specifier rather
        than an identifier expression:
        ``Patient.contained.all($this.is(Patient) implies age > 10)``
        """
        DeprecationWarning(
            "The is() function is supported for backwards compatibility "
            "with previous implementations of FHIRPath"
        )
        raise NotImplementedError

    def as_(self, type_cls: typing.Union[type, str]):
        """6.3.4. as(type : type specifier)
        The as() function is supported for backwards compatibility with
        previous implementations of FHIRPath. Just as with the as keyword,
        the type argument is an identifier that must resolve to the name of
        a type in a model. For implementations with compile-time typing,
        this requires special-case handling when processing the argument to
        treat is a type specifier rather than an identifier expression:
        ``
        Observation.component.where(value.as(Quantity) > 30 'mg')
        ``
        """
        DeprecationWarning(
            "The is() function is supported for backwards compatibility "
            "with previous implementations of FHIRPath"
        )

        raise NotImplementedError

    #   6.4. Collections
    def in_(self):
        """6.4.2. in (membership)
        If the left operand is a collection with a single item,
        this operator returns true if the item is in the right
        operand using equality semantics. If the left-hand side of the operator is
        empty, the result is empty,
        if the right-hand side is empty, the result is false.
        If the left operand has multiple items, an exception is thrown.

        The following example returns true if 'Joe'
        is in the list of given names for the Patient:
        ``
        'Joe' in Patient.name.given
        ``
        """
        raise NotImplementedError

    def contained(self):
        """6.4.3. contains (containership)
        If the right operand is a collection with a single item, this operator
        returns true if the item is in the left operand using equality semantics.
        If the right-hand side of the operator is empty, the result is empty,
        if the left-hand side is empty, the result is false.
        This is the converse operation of in.

        The following example returns true if the list of given names
        for the Patient has 'Joe' in it:

        ``Patient.name.given contains 'Joe'``
        """
        raise NotImplementedError

    #   10. Types and Reflection
    def get_type(self):
        """FHIRPath supports reflection to provide the ability for
        expressions to access type information describing the structure of values.
        The type() function returns the type information for each element of the
        input collection, using one of the following concrete subtypes of TypeInfo:
        """
        if self._type_info is None:
            self._assign_type_info()

        return self._type_info
