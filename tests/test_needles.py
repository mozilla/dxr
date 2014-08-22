from nose.tools import eq_, assert_raises


from dxr.plugins.needles import (unsparsify, by_line, group_needles,
                                 span_to_lines, pack)
from dxr.plugins.utils import Extent, Position

NEEDLE1 = ('x', Extent(Position(None, 0, 3), Position(None, 0, 7)))
NEEDLE2 = ('y', Extent(Position(None, 0, 5), Position(None, 2, 7)))
NEEDLE3 = ('z', Extent(Position(None, 0, 0), Position(None, -1, 0)))


def eq__(lis1, lis2):
    eq_(list(lis1), list(lis2))


def test_needle_smoke_test():
    eq__(unsparsify([]), [])


def test_unsparsify():
    assert_raises(ValueError, unsparsify, [NEEDLE3])

    output = [[pack('x', 3, 7), pack('y', 5, None)],
              [pack('y', 0, None)],
              [pack('y', 0, 7)]]

    eq__(output, unsparsify([NEEDLE1, NEEDLE2]))


def test_group_needles():
    eq__([], group_needles([]))

    fixture = [(pack('x', 3, 7), 0), (pack('y', 5, None), 0), (pack('y', 0, None), 1),
               (pack('y', 0, 7), 2)]

    output = [[pack('x', 3, 7), pack('y', 5, None)],
              [pack('y', 0, None)],
              [pack('y', 0, 7)]]
    eq__(output, group_needles(fixture))


def test_by_line():
    eq__([], by_line([]))
    eq__([(pack('x', 3, 7), 0),
          (pack('y', 5, None), 0),
          (pack('y', 0, None), 1),
          (pack('y', 0, 7), 2)],
         by_line([NEEDLE1, NEEDLE2]))


def test_span_to_lines():
    eq__(span_to_lines(NEEDLE1), [({'term': 'x', 'start': 3, 'end': 7}, 0)])
    eq__(span_to_lines(NEEDLE2), [({'term': 'y', 'start': 5, 'end': None}, 0),
                                  ({'term': 'y', 'start': 0, 'end': None}, 1),
                                  ({'term': 'y', 'start': 0, 'end': 7}, 2)])
    assert_raises(ValueError, lambda x: list(span_to_lines(x)), [])

