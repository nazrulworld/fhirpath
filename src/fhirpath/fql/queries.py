# _*_ coding: utf-8 _*_
import copy
import enum
import math

from zope.interface import implementer

from fhirpath.thirdparty import Proxy
from fhirpath.utils import FHIR_VERSION
from fhirpath.utils import builder
from fhirpath.utils import import_string
from fhirpath.utils import lookup_fhir_class_path

from .expressions import and_
from .expressions import fql
from .expressions import sort_
from .interfaces import IElementPath
from .interfaces import IQueryBuilder
from .interfaces import IQueryResult
from .interfaces import ISortTerm
from .interfaces import ITerm
from .navigator import PathNavigator
from .types import ElementPath
from .types import ModelFactory


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


@enum.unique
class CopyBehaviour(enum.Enum):

    FULL = enum.auto()
    BASE = enum.auto()


class Query(object):
    """ """

    @classmethod
    def _builder(cls, context=None):
        return QueryBuilder()

    @classmethod
    def from_(cls, resource, context=None):
        """
        """
        # xxx: return resource class
        return cls._builder(context).from_(resource)

    @classmethod
    def with_engine(cls, engine):
        """ """
        return cls._builder(engine)


@implementer(IQueryBuilder)
class QueryBuilder(object):
    """ """

    def __init__(self, engine=None):
        """ """
        self.engine = engine
        self.finalized = False
        self._limit = None
        self._offset = None

        self._from = []
        self._selects = []
        self._wheres = []
        self._sorts = []

    def bind(self, engine):
        """ """
        # might be clone
        self.engine = engine

    def clone(self):
        """ """
        return self.__copy__()

    def shadow_clone(self, behavior=CopyBehaviour.FULL):
        """Return proxy"""
        return self.__proxy__(behavior)

    def shadow_clone_base(self):
        """ """
        return self.shadow_clone(CopyBehaviour.BASE)

    def finalize(self, context=None):
        """ """
        if context:
            self.bind(context)

    def __copy__(self):
        """ """
        newone = self._copy_base()
        newone.engine = self.engine
        return newone

    def __proxy__(self, behavior: CopyBehaviour = CopyBehaviour.BASE):
        """ """
        newobj = CopyBehaviour.BASE and self._copy_base() or self.__copy__()
        proxied = Proxy().initialize(newobj)
        return proxied

    def _copy_base(self):
        """ """
        newone = type(self).__new__(type(self))
        newone.__dict__.update(self.__dict__)

        newone.finalized = self.finalized
        newone._limit = self._limit
        newone._offset = self._offset

        newone._from = copy(self._from)
        newone._selects = copy(self._selects)
        newone._wheres = copy(self._wheres)
        newone._sorts = copy(self._sorts)

        return newone

    @builder
    def from_(self, resource_type, alias=None):
        """ """
        model = QueryBuilder.create_model(resource_type)
        alias = alias or model.resource_type
        self._from.append((alias, model))

    @builder
    def select(self, *args):
        """ """
        for el_path in args:
            if IElementPath.providedBy(el_path):
                el_path = ElementPath(el_path)
            self._selects.append(el_path)

    @builder
    def where(self, *args, **kwargs):
        """ """
        if len(kwargs) > 0:
            for path, value in kwargs.items():

                term = and_(path, value)
                term.finalize(self)

                self._wheres.append(term)

        for term in args:
            assert ITerm.providedBy(term) is True
            term.finalize(self)

            self._wheres.append(term)

    @builder
    def limit(self, limit: int, offset: int = 0):
        """ """
        self._limit = limit
        self._offset = offset

    @builder
    def sort(self, *args):
        """ """
        for sort_path in args:
            if not ISortTerm.providedBy(sort_path):
                if isinstance(sort_path, (tuple, list)):
                    sort_path = sort_(*sort_path)
                else:
                    sort_path = sort_(sort_path)
            self._sorts.sppend(sort_path)

    @staticmethod
    def create_model(resource_type, fhir_version: FHIR_VERSION = FHIR_VERSION.DEFAULT):
        """ """
        klass = import_string(
            lookup_fhir_class_path(resource_type, fhir_release=fhir_version)
        )
        # xxx: should be cache?
        model = ModelFactory(f"{klass}Model", bases=(klass, PathNavigator), attrs={})
        return model

    def __fql__(self):
        """ """
        return fql(self.context.dialect.bind(self))

    def __str__(self):
        """ """
        return self.__fql__()

    def __call__(self, engine=None, **kw):
        """ """
        raise NotImplementedError


@implementer(IQueryResult)
class QueryResult(object):
    """ """
    def fetchall(self):
        """ """

    def single(self):
        """Will return the single item in the input if there is just one item.
        If the input collection is empty ({ }), the result is empty.
        If there are multiple items, an error is signaled to the evaluation environment.
        This operation is useful for ensuring that an error is returned
        if an assumption about cardinality is violated at run-time."""

    def first(self):
        """Returns a collection containing only the first item in the input collection.
        This function is equivalent to item(0), so it will return an empty collection
        if the input collection has no items."""

    def last(self):
        """Returns a collection containing only the last item in the input collection.
        Will return an empty collection if the input collection has no items."""

    def tail(self):
        """Returns a collection containing all but the first item in the input
        collection. Will return an empty collection
        if the input collection has no items, or only one item."""

    def skip(self, num: int):
        """Returns a collection containing all but the first num items
        in the input collection. Will return an empty collection
        if there are no items remaining after the indicated number of items have
        been skipped, or if the input collection is empty.
        If num is less than or equal to zero, the input collection
        is simply returned."""

    def take(self, num: int):
        """Returns a collection containing the first num items in the input collection,
        or less if there are less than num items. If num is less than or equal to 0, or
        if the input collection is empty ({ }), take returns an empty collection."""

    def count(self):
        """Returns a collection with a single value which is the integer count of
        the number of items in the input collection.
        Returns 0 when the input collection is empty."""

    def empty(self):
        """Returns true if the input collection is empty ({ }) and false otherwise."""
        return self.count() == 0

    def __len__(self):
        """ """
        return self.count()

    def __getitem__(self, key):
        """
        Lazy loading es results with negative index support.
        We store the results in buckets of what the bulk size is.
        This is so you can skip around in the indexes without needing
        to load all the data.
        Example(all zero based indexing here remember):
            (525 results with bulk size 50)
            - self[0]: 0 bucket, 0 item
            - self[10]: 0 bucket, 10 item
            - self[50]: 50 bucket: 0 item
            - self[55]: 50 bucket: 5 item
            - self[352]: 350 bucket: 2 item
            - self[-1]: 500 bucket: 24 item
            - self[-2]: 500 bucket: 23 item
            - self[-55]: 450 bucket: 19 item
        """
        if isinstance(key, slice):
            return [self[i] for i in range(key.start, key.end)]
        else:
            if key + 1 > self.count:
                raise IndexError
            elif key < 0 and abs(key) > self.count:
                raise IndexError

            if key >= 0:
                result_key = (key / self.bulk_size) * self.bulk_size
                start = result_key
                result_index = key % self.bulk_size
            elif key < 0:
                last_key = (
                    int(math.floor(float(self.count) / float(self.bulk_size)))
                    * self.bulk_size
                )
                start = result_key = last_key - (
                    (abs(key) / self.bulk_size) * self.bulk_size
                )
                if last_key == result_key:
                    result_index = key
                else:
                    result_index = (key % self.bulk_size) - (
                        self.bulk_size - (self.count % last_key)
                    )

            if result_key not in self.results:
                self.results[result_key] = self.es._search(
                    self.query, sort=self.sort, start=start, **self.query_params
                )["hits"]["hits"]

            return self.results[result_key][result_index]

        def __iter__(self):
            """ """
            pass
