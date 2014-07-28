from nose.tools import eq_


from dxr.plugins.needles import (unsparsify, by_line, group_needles,
                                 span_to_lines)
from dxr.plugins.utils import Extent, Position

NEEDLE1 = ('x', Extent(Position(None, 0, 0), Position(None, 0, 0)))
NEEDLE2 = ('y', Extent(Position(None, 0, 0), Position(None, 2, 0)))
NEEDLE3 = ('z', Extent(Position(None, 0, 0), Position(None, -1, 0)))


def eq__(lis1, lis2):
    eq_(list(lis1), list(lis2))


def test_needle_smoke_test():
    eq__(unsparsify([]), [])


def test_unsparsify():
    eq__([], unsparsify([]))
    eq__([], unsparsify([NEEDLE3]))
    eq__([[('x', 0), ('y', 0)], [('y', 1)], [('y', 2)]],
         unsparsify([NEEDLE1, NEEDLE2]))
    eq__([[('y', 0), ('x', 0)], [('y', 1)], [('y', 2)]],
         unsparsify([NEEDLE2, NEEDLE1]))


def test_group_needles():
    eq__([], group_needles([]))
    eq__([[('x', 0), ('y', 0)], [('y', 1)], [('y', 2)]],
         group_needles([('x', 0), ('y', 0), ('y', 1), ('y', 2)]))
    eq__([[('y', 0), ('x', 0)], [('y', 1)], [('y', 2)]],
         group_needles([('y', 0), ('y', 1), ('y', 2), ('x', 0)]))


def test_by_line():
    eq__([], by_line([]))
    eq__([], by_line([NEEDLE3]))
    eq__([('x', 0), ('y', 0), ('y', 1), ('y', 2)],
         by_line([NEEDLE1, NEEDLE2]))


def test_span_to_lines():
    eq__(span_to_lines(NEEDLE1), [('x', 0)])
    eq__(span_to_lines(NEEDLE2), [('y', 0), ('y', 1), ('y', 2)])
    eq__(span_to_lines(NEEDLE3), [])
