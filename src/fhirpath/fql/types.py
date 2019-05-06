# _*_ coding: utf-8 _*_
from fhir.resources.fhirelementfactory import FHIRElementFactory

from fhirpath.thirdparty import Proxy


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


class Model(Proxy):
    """ """

    def __init__(self, resource_type):
        """ """
        super(Model, self).__init__()
        model = FHIRElementFactory.instantiate(resource_type)
        self.initialize(model)


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
