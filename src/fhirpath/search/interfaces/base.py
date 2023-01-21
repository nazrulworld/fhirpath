# _*_ coding: utf-8 _*_
from zope.interface import Attribute, Interface

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


class IBaseClass(Interface):
    """ """

    _finalized = Attribute("Finalized Flag")

    def finalize(context):
        """ """


class ICloneable(Interface):
    """ """

    def clone():
        """ """

    def __copy__():
        """"""


class IStorage(Interface):
    """ """

    _last_updated = Attribute("Last Updated")
    _write_locked = Attribute("Write Locked")
    _read_locked = Attribute("Read Locked")

    def get(item):
        """ """

    def set(item, value):
        """ """

    def insert(item, value):
        """ """

    def delete(item):
        """ """

    def clear():
        """ """

    def exists(item):
        """ """

    def empty():
        """ """

    def total():
        """ """


class IFhirPrimitiveType(Interface):
    """ """

    __visit_name__ = Attribute("visit name")
    __regex__ = Attribute("Regex")

    def to_python():
        """ """

    def to_json():
        """ """


class IPrimitiveTypeCollection(Interface):
    """ """

    def add(item):
        """ """

    def remove(item=None, index=None):
        """ """


class ITypeSpecifier(Interface):
    """ """


class ITypeInfoWithElements(Interface):
    """ """

    def get_elements():
        """ """


class IPathInfoContext(Interface):
    """ """

    fhir_release = Attribute("FHIR Release")
    prop_name = Attribute("Property Name")
    prop_original = Attribute("Original propety name")
    type_name = Attribute("Type Name")
    type_class = Attribute("Type Class")
    optional = Attribute("Optional")
    multiple = Attribute("Multiple")


class IModel(Interface):
    """FHIR Model Class"""


# --------------*-----------------
# ´´search.py``
class ISearch(Interface):
    """ """


class ISearchContext(Interface):
    """ """


class ISearchContextFactory(Interface):
    """ """


class IFhirSearch(Interface):
    """ """


# --------------*-----------------
# ´´query.py``
class IQuery(IBaseClass):
    """ """

    fhir_release = Attribute("FHIR Release Name")


class IQueryBuilder(IBaseClass):
    """ """

    context = Attribute("Fhir Query Context")

    def bind(context):
        """ """


class IQueryResult(Interface):
    """ """

    def fetchall():  # lgtm[py/not-named-self]
        """ """

    def single():  # lgtm[py/not-named-self]
        """Will return the single item in the input if there is just one item.
        If the input collection is empty ({ }), the result is empty.
        If there are multiple items, an error is signaled to the evaluation environment.
        This operation is useful for ensuring that an error is returned
        if an assumption about cardinality is violated at run-time."""

    def first():  # lgtm[py/not-named-self]
        """Returns a collection containing only the first item in the input collection.
        This function is equivalent to item(0), so it will return an empty collection
        if the input collection has no items."""

    def last():  # lgtm[py/not-named-self]
        """Returns a collection containing only the last item in the input collection.
        Will return an empty collection if the input collection has no items."""

    def tail():
        """Returns a collection containing all but the first item in the input
        collection. Will return an empty collection
        if the input collection has no items, or only one item."""

    def skip(num: int):  # lgtm[py/not-named-self]
        """Returns a collection containing all but the first num items
        in the input collection. Will return an empty collection
        if there are no items remaining after the indicated number of items have
        been skipped, or if the input collection is empty.
        If num is less than or equal to zero, the input collection
        is simply returned."""

    def take(num: int):  # lgtm[py/not-named-self]
        """Returns a collection containing the first num items in the input collection,
        or less if there are less than num items. If num is less than or equal to 0, or
        if the input collection is empty ({ }), take returns an empty collection."""

    def count():  # lgtm[py/not-named-self]
        """Returns a collection with a single value which is the integer count of
        the number of items in the input collection.
        Returns 0 when the input collection is empty."""

    def empty():  # lgtm[py/not-named-self]
        """Returns true if the input collection is empty ({ }) and false otherwise."""


class IIgnoreModifierCheck(Interface):
    """ """


class IIgnoreNotModifierCheck(IIgnoreModifierCheck):
    """ """
