# _*_ coding: utf-8 _*_
import math
from copy import copy

from zope.interface import implementer

from fhirpath.exceptions import ConstraintNotSatisfied
from fhirpath.exceptions import ValidationError
from fhirpath.thirdparty import Proxy
from fhirpath.utils import FHIR_VERSION
from fhirpath.utils import Model
from fhirpath.utils import builder

from .constraints import required_finalized
from .constraints import required_from_resource
from .constraints import required_not_finalized
from .expressions import and_
from .expressions import fql
from .expressions import sort_
from .interfaces import IElementPath
from .interfaces import IGroupTerm
from .interfaces import IQuery
from .interfaces import IQueryBuilder
from .interfaces import IQueryResult
from .interfaces import ISortTerm
from .interfaces import ITerm
from .types import ElementPath
from .types import FromClause
from .types import LimitClause
from .types import SelectClause
from .types import SortClause
from .types import WhereClause


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


@implementer(IQuery)
class Query(object):
    """ """

    def __init__(
        self,
        fhir_relase: FHIR_VERSION,
        from_: FromClause,
        select: SelectClause,
        where: WhereClause,
        sort: SortClause,
        limit: LimitClause,
    ):
        """ """

        self.fhir_relase = fhir_relase
        self._from = from_
        self._select = select
        self._where = where
        self._sort = sort
        self._limit = limit

    @classmethod
    def _builder(cls, engine=None):
        return QueryBuilder(engine)

    @classmethod
    def from_builder(cls, builder):
        """Create Query object from QueryBuilder.
        Kind of reverse process"""
        if not IQueryBuilder(builder)._finalized:
            raise ConstraintNotSatisfied(
                "QueryBuilder object must be in finalized state"
            )
        query = cls(
            builder._engine.fhir_release,
            builder._from,
            builder._select,
            builder._where,
            builder._sort,
            builder._limit,
        )
        return query

    def get_where(self):
        """ """
        return self._where

    def get_from(self):
        """ """
        return self._from

    def get_select(self):
        """ """
        return self._select

    def get_sort(self):
        """ """
        return self._sort

    def get_limit(self):
        """ """
        return self._limit

    def __proxy__(self):
        """ """
        proxied = Proxy().initialize(self)
        return proxied


@implementer(IQueryBuilder)
class QueryBuilder(object):
    """ """

    def __init__(self, engine=None):
        """ """
        self._engine = engine
        self._finalized = False

        self._from = FromClause()
        self._select = SelectClause()
        self._where = WhereClause()
        self._sort = SortClause()
        self._limit = LimitClause()

    def bind(self, engine):
        """ """
        # might be clone
        self._engine = engine

    def clone(self):
        """ """
        return self.__copy__()

    def finalize(self, engine=None):
        """ """
        self._pre_check()

        if engine:
            self.bind(engine)

        if self._engine is None:
            raise ConstraintNotSatisfied(
                "Object from '{0!s}' must be binded with engine".format(
                    self.__class__.__name__
                )
            )
        # xxx: do any validation?
        if len(self._select) == 0:
            el_path = ElementPath("*")
            self._select.append(el_path)

        # Finalize path elements
        [se.finalize(self._engine) for se in self._select]

        # Finalize where terms on demand
        [wr.finalize(self._engine) for wr in self._where]

        # Finalize sorts ondemand
        [sr.finalize(self._engine) for sr in self._sort]

        self._validate()

        self._finalized = True

    def __copy__(self):
        """ """
        newone = type(self).__new__(type(self))
        newone.__dict__.update(self.__dict__)

        newone._finalized = self._finalized
        newone._engine = self._engine

        newone._limit = copy(self._limit)
        newone._from = copy(self._from)
        newone._select = copy(self._select)
        newone._where = copy(self._where)
        newone._sort = copy(self._sort)

        return newone

    @builder
    def from_(self, resource_type, alias=None):
        """ """
        required_not_finalized(self)

        if len(self._from) > 0:
            # info: we are allowing single resource only
            raise ValidationError("from_ value already assigned!")

        model = Model.create(resource_type)
        alias = alias or model.resource_type
        self._from.append((alias, model))

    @builder
    def select(self, *args):
        """ """
        self._pre_check()

        for el_path in args:
            if not IElementPath.providedBy(el_path):
                el_path = ElementPath(el_path)
            # Make sure correct root path
            if not el_path.star:
                self._validate_root_path(str(el_path))
            self._select.append(el_path)

    @builder
    def where(self, *args, **kwargs):
        """ """
        self._pre_check()

        if len(kwargs) > 0:
            for path, value in kwargs.items():
                term = and_(path, value)

                self._validate_term_path(term)
                self._where.append(term)

        for term in args:
            assert ITerm.providedBy(term) is True

            self._validate_term_path(term)
            self._where.append(term)

    @builder
    def limit(self, limit: int, offset: int = 0):
        """ """
        self._pre_check()
        self._limit.limit = limit
        self._limit.offset = offset

    @builder
    def sort(self, *args):
        """ """
        self._pre_check()

        for sort_path in args:
            if not ISortTerm.providedBy(sort_path):
                if isinstance(sort_path, (tuple, list)):
                    sort_path = sort_(*sort_path)
                else:
                    sort_path = sort_(sort_path)
            self._sort.append(sort_path)

    def get_query(self):
        """ """
        required_finalized(self)

        return Query.from_builder(self)

    def __fql__(self):
        """ """
        required_finalized(self)

        return fql(self.context.dialect.bind(self))

    def __str__(self):
        """ """
        required_finalized(self)

        return self.__fql__()

    def __call__(self, unrestricted=False, engine=None, async_result=False):
        """ """
        if not self._finalized and (engine or self._engine):
            self.finalize(engine)

        query = self.get_query()
        result_factory = QueryResult
        if async_result is True:
            result_factory = AsyncQueryResult

        result = result_factory(
            query=query, engine=self._engine, unrestricted=unrestricted
        )
        return result

    def _pre_check(self):
        """ """
        required_from_resource(self)
        required_not_finalized(self)

    def _validate(self):
        """ """
        # validate select elements
        if any([el.star for el in self._select]) and len(self._select) > 1:
            raise ValidationError("select(*) cannot co-exists other select element!")

    def _validate_root_path(self, path_string):
        """ """
        match = False
        for alias, model in self._from:
            if path_string.split(".")[0] == alias:
                match = True
                break
        if match is False:
            raise ValidationError(
                "Root path '{0!s}' must be matched with from models".format(
                    path_string.split(".")[0]
                )
            )

    def _validate_term_path(self, term):
        """ """
        if IGroupTerm.providedBy(term):
            for trm in term.terms:
                self._validate_term_path(trm)
        else:
            self._validate_root_path(str(term.path))


@implementer(IQueryResult)
class QueryResult(object):
    """ """

    def __init__(self, query: Query, engine, unrestricted=False):
        """ """
        self._query = query
        self._engine = engine
        self._unrestricted = unrestricted

    def fetchall(self):
        """ """
        pass

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

    def OFF__getitem__(self, key):
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


class AsyncQueryResult(QueryResult):
    """ """

    async def fetchall(self):
        """ """
        result = await self._engine.execute(self._query, self._unrestricted)
        return result

    async def __aiter__(self):
        """ """
        result = await self._engine.execute(self._query, self._unrestricted)
        model_class = self._query.get_from()[0][1]
        for item in result.body:
            yield model_class(item)


def Q_(resource=None, engine=None):
    """ """
    builder = Query._builder(engine)
    if resource is not None:
        builder = builder.from_(resource)
    return builder
