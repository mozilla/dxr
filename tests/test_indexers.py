from nose import SkipTest
from nose.tools import eq_, assert_raises

from dxr.indexers import (unsparsify, by_line, group_needles, span_to_lines,
                          key_object_pair, Extent, Position, split_into_lines,
                          FileToSkim)


KV1 = ('x', 'v1')
KV2 = ('y', 'v2')
KV3 = ('z', 'v3')

NEEDLE1 = (KV1, Extent(Position(1, 3), Position(1, 7)))
NEEDLE2 = (KV2, Extent(Position(1, 5), Position(3, 7)))
NEEDLE3 = (KV3, Extent(Position(1, 0), Position(0, 0)))


def list_eq(result, expected):
    eq_(list(result), list(expected))


def test_needle_smoke_test():
    list_eq(unsparsify(lambda: [])(), [])


def test_unsparsify_invalid():
    """Make sure unsparify raises ValueError on extents whose ends come before
    their starts."""
    raise SkipTest("At the moment, we tolerate these and simply warn. Once the clang compiler plugin doesn't spit these out anymore, return to raising an exception.")
    assert_raises(ValueError, unsparsify(lambda: [NEEDLE3]))


def test_unsparsify():
    # Test 2 overlapping dense needles:
    output = [[key_object_pair(KV1, 3, 7), key_object_pair(KV2, 5, None)],  # the overlap.
              [key_object_pair(KV2, 0, None)],  # just the second one,
              [key_object_pair(KV2, 0, 7)]]     # extending beyond the first

    list_eq(unsparsify(lambda: [NEEDLE1, NEEDLE2])(), output)


def test_group_needles():
    list_eq(group_needles([]), [])
    list_eq(group_needles([('A', 1), ('B', 1), ('C', 2), ('D', 3)]),
                          [['A', 'B'],
                           ['C'],
                           ['D']])


def test_by_line():
    list_eq(by_line([]), [])
    list_eq(by_line([NEEDLE1, NEEDLE2]),
            [(key_object_pair(KV1, 3, 7), 1),
             (key_object_pair(KV2, 5, None), 1),
             (key_object_pair(KV2, 0, None), 2),
             (key_object_pair(KV2, 0, 7), 3)])


def test_span_to_lines():
    list_eq(span_to_lines(NEEDLE1),
            [((('x', 'v1'), 3, 7), 1)])
    list_eq(span_to_lines(NEEDLE2),
            [((('y', 'v2'), 5, None), 1),
             ((('y', 'v2'), 0, None), 2),
             ((('y', 'v2'), 0, 7), 3)])
    assert_raises(ValueError, lambda x: list(span_to_lines(x)), [])


def test_split_into_lines():
    list_eq(split_into_lines([('k', {'m': 'ap'}, Extent(Position(1, 5), Position(3, 7)))]),
        [('k', {'m': 'ap'}, Extent(Position(1, 5), Position(1, None))),
         ('k', {'m': 'ap'}, Extent(Position(2, 0), Position(2, None))),
         ('k', {'m': 'ap'}, Extent(Position(3, 0), Position(3, 7)))])


def test_char_offset():
    """Make sure char_offset() deals with different kinds of line breaks and
    handles the first and last lines correctly."""
    skimmer = FileToSkim('/some/path', u'abc\r\nde\nfghi', 'dummy_plugin', 'dummy_tree')
    eq_(skimmer.char_offset(1, 1), 1)
    eq_(skimmer.char_offset(2, 1), 6)
    eq_(skimmer.char_offset(3, 1), 9)
