# _*_ coding: utf-8 _*_

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class BaseType(object):
    """ """
    def __init__(self, max_=None, min_=None, type_code=None, type_=None):
        """ """
        self._max = max_
        self._min = min_
        self.__visit_name__ = type_code
        self._type = type_

    @property
    def is_array(self):
        """ """
        return self._max == "*"
