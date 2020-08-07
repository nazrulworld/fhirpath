# _*_ coding: utf-8 _*_
from collections import defaultdict
from datetime import datetime
from typing import Optional

from zope.interface import implementer

from .enums import FHIR_VERSION
from .interfaces import IStorage
from .types import EMPTY_VALUE

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"


@implementer(IStorage)
class MemoryStorage(defaultdict):
    """ """

    _last_updated: Optional[datetime]
    _write_locked: Optional[bool]
    _read_locked: Optional[bool]

    def get(self, item, default=EMPTY_VALUE):
        """ """
        try:
            return self[item]
        except KeyError:
            if default is EMPTY_VALUE:
                raise
            return default

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


FHIR_RESOURCE_CLASS_STORAGE: MemoryStorage = MemoryStorage()
PATH_INFO_STORAGE: MemoryStorage = MemoryStorage()
SEARCH_PARAMETERS_STORAGE: MemoryStorage = MemoryStorage()
FHIR_RESOURCE_SPEC_STORAGE: MemoryStorage = MemoryStorage()

releases = set([member.name for member in FHIR_VERSION if member.name != "DEFAULT"])
for release in releases:
    if not PATH_INFO_STORAGE.exists(release):
        PATH_INFO_STORAGE.insert(release, MemoryStorage())

    if not FHIR_RESOURCE_CLASS_STORAGE.exists(release):
        FHIR_RESOURCE_CLASS_STORAGE.insert(release, MemoryStorage())

    if not SEARCH_PARAMETERS_STORAGE.exists(release):
        SEARCH_PARAMETERS_STORAGE.insert(release, MemoryStorage())

    if not FHIR_RESOURCE_SPEC_STORAGE.exists(release):
        FHIR_RESOURCE_SPEC_STORAGE.insert(release, MemoryStorage())
del releases
