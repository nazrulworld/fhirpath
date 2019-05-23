# _*_ coding: utf-8 _*_
from collections import defaultdict

from zope.interface import implementer

from .interfaces import IStorage


__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


@implementer(IStorage)
class MemoryStorage(defaultdict):
    """ """

    _last_updated = None
    _write_locked = None
    _read_locaked = None

    def insert(self, item, value):
        """ """
        self[item] = value

    def delete(self, item):
        """ """
        del self[item]

    def exists(self, item):
        """ """
        return item in self

    def empty(self):
        """ """
        return len(self) == 0

    def total(self):
        """ """
        return len(self)


FHIR_RESOURCE_CLASS_STORAGE = MemoryStorage()
PATH_INFO_STORAGE = MemoryStorage()
