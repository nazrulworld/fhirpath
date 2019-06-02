# _*_ coding: utf-8 _*_
import enum


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class FHIR_VERSION(enum.Enum):
    """ """

    DEFAULT = "R4"
    STU3 = "STU3"
    R4 = "R4"
    DSTU2 = "DSTU2"


@enum.unique
class SortOrderType(enum.Enum):
    """ """

    ASC = "asc"
    DESC = "desc"


@enum.unique
class MatchType(enum.Enum):
    """ """

    ANY = "ANY"
    ALL = "ALL"
    ONE = "ONE"
