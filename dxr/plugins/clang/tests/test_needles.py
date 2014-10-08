from nose.tools import eq_, assert_raises

from dxr.indexers import (unsparsify, by_line, group_needles, span_to_lines,
                          key_object_pair, Extent, Position)


KV1 = ('x', 'v1')
KV2 = ('y', 'v2')
KV3 = ('z', 'v3')

NEEDLE1 = (KV1, Extent(Position(None, 1, 3), Position(None, 1, 7)))
NEEDLE2 = (KV2, Extent(Position(None, 1, 5), Position(None, 3, 7)))
NEEDLE3 = (KV3, Extent(Position(None, 1, 0), Position(None, 0, 0)))


def list_eq(result, expected):
    eq_(list(result), list(expected))


def test_needle_smoke_test():
    list_eq(unsparsify([]), [])


def test_unsparsify():
    assert_raises(ValueError, unsparsify, [NEEDLE3])

    # Test 2 overlapping dense needles:
    output = [[key_object_pair(KV1, 3, 7), key_object_pair(KV2, 5, None)],  # the overlap.
              [key_object_pair(KV2, 0, None)],  # just the second one,
              [key_object_pair(KV2, 0, 7)]]     # extending beyond the first

    list_eq(unsparsify([NEEDLE1, NEEDLE2]), output)


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
