# _*_ coding: utf-8 _*_
import copy

from fhirpath.utils import FHIR_VERSION
from fhirpath.utils import builder
from fhirpath.utils import fql
from fhirpath.utils import import_string
from fhirpath.utils import lookup_fhir_class_path

from .expressions import and_
from .interfaces import ITerm
from .navigator import PathNavigator
from .types import ModelFactory


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class DateQuery(object):
    """ """


class DateTimeQuery(object):
    """ """


class TokenQuery(object):
    """ """


class NumberQuery(object):
    """ """


class QuantityQuery(object):
    """ """


class URIQuery(object):
    """ """


class ReferenceQuery(object):
    """ """


class ExistsQuery(object):
    """ """


class BooleanQuery(object):
    """ """


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
    def with_context(cls, context):
        """ """
        return cls._builder(context)


class QueryBuilder(object):
    """ """

    def __init__(self, context=None):
        """ """
        self.context = context
        self._from = []
        self._selects = []
        self._distinct = False

        self._wheres = None
        self._orderbys = []
        self._limit = None
        self._offset = None
        self._select_star = False

    def bind(self, context):
        """ """
        # might be clone
        self.context = context

    def __copy__(self):
        """ """
        newone = type(self).__new__(type(self))
        newone.__dict__.update(self.__dict__)
        newone._select_star = copy(self._select_star)
        newone._from = copy(self._from)
        newone.context = copy(self.context)
        newone._selects = copy(self._selects)
        newone._columns = copy(self._columns)
        newone._values = copy(self._values)
        newone._groupbys = copy(self._groupbys)
        newone._orderbys = copy(self._orderbys)
        newone._joins = copy(self._joins)
        newone._unions = copy(self._unions)
        newone._updates = copy(self._updates)
        return newone

    @builder
    def from_(self, resource_type, alias=None):
        """ """
        model = QueryBuilder.create_model(resource_type)
        alias = alias or model.resource_type
        self._from.append((alias, model))

    @builder
    def select(self, *args, **kw):
        """ """

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

    def __iter__(self):
        """ """
        for res in self.context.engine.query(self):
            yield res
