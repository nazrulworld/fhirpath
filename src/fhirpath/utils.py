# _*_ coding: utf-8 _*_
import sys


__author__ = "Md Nazrul Islam<email2nazrul@gmail.com>"


def _reraise(tp, value, tb=None):
    if value is None:
        value = tp
    if value.__traceback__ is not tb:
        raise value.with_traceback(tb)
    raise value


def reraise(klass, msg=None, callback=None, **kw):
    """Reraise custom exception class"""
    if not issubclass(klass, Exception):
        raise RuntimeError(f"Class ``{klass}`` must be derrived from Exception class.")
    t, v, tb = sys.exc_info()
    msg = msg or str(v)
    try:
        instance = klass(msg, **kw)
        if callable(callback):
            instance = callback(instance)

        _reraise(instance, None, tb)
    finally:
        del t, v, tb
