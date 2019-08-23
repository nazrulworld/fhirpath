# _*_ coding: utf-8 _*_
from .url import _parse_rfc1738_args


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def make_url(connection_str):
    """ """
    return _parse_rfc1738_args(connection_str)
