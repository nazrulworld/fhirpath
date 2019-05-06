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


def fql(obj):
    """ """
    try:
        func = getattr(obj, "__fql__")
        try:
            getattr(func, "__self__")
        except AttributeError:
            reraise(
                ValueError, "__fql__ is not bound method, make sure class initialized!"
            )

        return func()
    except AttributeError:
        raise AttributeError("Object must have __fql__ method available")


def builder(func):
    """
    Decorator for wrapper "builder" functions.  These are functions on the
    Query class or other classes used for building queries which mutate the
    query and return self.  To make the build functions immutable, this decorator is
    used which will deepcopy the current instance.
    This decorator will return the return value of the inner function
    or the new copy of the instance.  The inner function does not need to return self.
    """
    import copy

    def _copy(self, *args, **kwargs):
        self_copy = copy.copy(self)
        result = func(self_copy, *args, **kwargs)

        # Return self if the inner function returns None.
        # This way the inner function can return something
        # different (for example when creating joins, a different builder is returned).
        if result is None:
            return self_copy

        return result

    return _copy
