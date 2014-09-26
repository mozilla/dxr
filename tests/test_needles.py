from nose.tools import eq_, assert_raises


from dxr.plugins.needles import (unsparsify, by_line, group_needles,
                                 span_to_lines, pack)
from dxr.plugins.utils import Extent, Position

KV1 = ('x', 'v1')
KV2 = ('y', 'v2')
KV3 = ('z', 'v3')

NEEDLE1 = (KV1, Extent(Position(None, 1, 3), Position(None, 1, 7)))
NEEDLE2 = (KV2, Extent(Position(None, 1, 5), Position(None, 3, 7)))
NEEDLE3 = (KV3, Extent(Position(None, 1, 0), Position(None, 0, 0)))


def eq__(lis1, lis2):
    eq_(list(lis1), list(lis2))


def test_needle_smoke_test():
    eq__(unsparsify([]), [])


def test_unsparsify():
    assert_raises(ValueError, unsparsify, [NEEDLE3])

    output = [[pack(KV1, 3, 7), pack(KV2, 5, None)],
              [pack(KV2, 0, None)],
              [pack(KV2, 0, 7)]]

    eq__(output, unsparsify([NEEDLE1, NEEDLE2]))


def test_group_needles():
    eq__([], group_needles([]))

    fixture = [(pack(KV1, 3, 7), 1), (pack(KV2, 5, None), 1), (pack(KV2, 0, None), 2),
               (pack(KV2, 0, 7), 3)]

    output = [[pack(KV1, 3, 7), pack(KV2, 5, None)],
              [pack(KV2, 0, None)],
              [pack(KV2, 0, 7)]]
    eq__(output, group_needles(fixture))


def test_by_line():
    eq__([], by_line([]))
    eq__([(pack(KV1, 3, 7), 1),
          (pack(KV2, 5, None), 1),
          (pack(KV2, 0, None), 2),
          (pack(KV2, 0, 7), 3)],
         by_line([NEEDLE1, NEEDLE2]))


def test_span_to_lines():
    eq__(span_to_lines(NEEDLE1), [(('x', {'value': 'v1', 'start': 3, 'end': 7}), 1)])
    eq__(span_to_lines(NEEDLE2), [(('y', {'value': 'v2', 'start': 5, 'end': None}), 1),
                                  (('y', {'value': 'v2', 'start': 0, 'end': None}), 2),
                                  (('y', {'value': 'v2', 'start': 0, 'end': 7}), 3)])
    assert_raises(ValueError, lambda x: list(span_to_lines(x)), [])
