from nose.tools import eq_

from dxr.plugins.core import _find_iter


def list_eq(iterable, list_):
    """Reify an iterable into a list, and compare it to a second list."""
    eq_(list(iterable), list_)


def test_find_iter():
    list_eq(_find_iter('haystack', 'hay'), [0])
    list_eq(_find_iter('heyhey', 'hey'), [0, 3])
    list_eq(_find_iter('heyhey', ''), [])
    list_eq(_find_iter('hhhhh', 'hh'), [0, 2])  # Don't report overlaps.
