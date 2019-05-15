# _*_ coding: utf-8 _*_
import copy
import enum

from zope.interface import implementer

from fhirpath.thirdparty import Proxy
from fhirpath.utils import FHIR_VERSION
from fhirpath.utils import builder
from fhirpath.utils import fql
from fhirpath.utils import import_string
from fhirpath.utils import lookup_fhir_class_path

from .expressions import and_
from .expressions import sort_
from .interfaces import IElementPath
from .interfaces import IQueryBuilder
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
    def with_context(cls, context):
        """ """
        return cls._builder(context)


@implementer(IQueryBuilder)
class QueryBuilder(object):
    """ """

    def __init__(self, context=None):
        """ """
        self.context = context
        self.finalized = False
        self._limit = None
        self._offset = None

        self._from = []
        self._selects = []
        self._wheres = []
        self._sorts = []

    def bind(self, context):
        """ """
        # might be clone
        self.context = context

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
        newone.context = self.context
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

    def __iter__(self):
        """ """
        for res in self.context.engine.query(self):
            yield res
