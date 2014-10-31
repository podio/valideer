import sys

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

if PY2:  # pragma: no cover
    string_types = basestring
    int_types = (int, long)
    from itertools import izip, imap
    long = long
    unicode = unicode
    xrange = xrange
    iteritems = dict.iteritems
else:  # pragma: no cover
    string_types = str
    int_types = (int,)
    izip = zip
    imap = map
    long = int
    unicode = str
    iteritems = dict.items
    xrange = range


def with_metaclass(mcls):
    def decorator(cls):
        body = vars(cls).copy()
        # clean out class body
        body.pop('__dict__', None)
        body.pop('__weakref__', None)
        return mcls(cls.__name__, cls.__bases__, body)
    return decorator
