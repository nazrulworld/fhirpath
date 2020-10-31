# _*_ coding: utf-8 _*_
from zope.interface import Invalid

from fhirpath.utils import import_string, reraise

from .url import _parse_rfc1738_args

__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def make_url(connection_str):
    """ """
    return _parse_rfc1738_args(connection_str)


def create_connection(conn_string, klass=None, **extra):
    """ """
    mod_pattern = "fhirpath.connectors.factory.{driver_mod}.create"
    if isinstance(conn_string, (tuple, list)):
        url = [make_url(conn) for conn in conn_string]
        url_ = url[0]
    else:
        url_ = url = make_url(conn_string)

    driver_mod = url_.drivername.split("+")[0]
    try:
        factory = import_string(mod_pattern.format(driver_mod=driver_mod))
        return factory(url, klass, **extra)
    except ImportError:
        reraise(
            Invalid,
            "Invalid ({0}) drivername or not supported yet!.".format(url_.drivername),
        )
