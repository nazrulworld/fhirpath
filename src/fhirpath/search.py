# _*_ coding: utf-8 _*_
from urllib.parse import unquote_plus

from multidict import MultiDict
from multidict import MultiDictProxy
from zope.interface import Invalid
from zope.interface import implementer

from fhirpath.interfaces import ISearch
from fhirpath.interfaces import ISearchContext
from fhirpath.thirdparty import at_least_one_of
from fhirpath.thirdparty import mutually_exclusive_parameters


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


@implementer(ISearchContext)
class SearchContext(object):
    """ """

    __slots__ = ("resource_name", "engine", )


@implementer(ISearch)
class Search(object):
    """ """

    @at_least_one_of("query_string", "params")
    @mutually_exclusive_parameters("query_string", "params")
    def __init__(self, context, query_string=None, params=None):
        """ """
        self.context = ISearchContext(context)
        if query_string:
            self.search_params = Search.parse_query_string(query_string, False)
        elif isinstance(params, (tuple, list)):
            mdict = MultiDict(params)
            self.search_params = MultiDictProxy(mdict)
        elif isinstance(params, dict):
            mdict = MultiDict(params.items())
            self.search_params = MultiDictProxy(mdict)
        elif isinstance(params, MultiDictProxy):
            self.search_params = params
        else:
            raise Invalid

    @staticmethod
    def parse_query_string(query_string, allow_none=False):
        """
        param:request
        param:allow_none
        """
        params = MultiDict()

        for q in query_string.split("&"):
            parts = q.split("=")
            param_name = unquote_plus(parts[0])
            try:
                value = parts[1] and unquote_plus(parts[1]) or None
            except IndexError:
                if not allow_none:
                    continue
                value = None

            params.add(param_name, value)

        return MultiDictProxy(params)

    @classmethod
    def from_query_string(cls, query_string):
        """ """

    def __iter__(self):
        """ """
