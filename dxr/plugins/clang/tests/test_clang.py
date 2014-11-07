"""Unit tests for clang plugin

Most of these have been deleted in favor of integration tests elsewhere, and
we can probably go further in that direction.

"""
import csv
from itertools import ifilter
from StringIO import StringIO

from nose.tools import eq_

from dxr.indexers import Extent, Position, FuncSig
from dxr.plugins.clang.condense import condense, DISPATCH_TABLE
from dxr.plugins.clang.needles import sig_needles


DEFAULT_EXTENT = Extent(start=Position(0, 0, 0), end=Position(0, 0, 0))


def get_csv(csv_str):
    return condense(csv.reader(StringIO('\n'.join(ifilter(None, (x.strip() for x in csv_str.splitlines()))))),
                    DISPATCH_TABLE)


def test_smoke_test_csv():
    get_csv('')


def eq__(l1, l2):
    eq_(list(l1), list(l2))


def test_sig_needles():
    fixture = {
        'function': [{'type': FuncSig(('int**', 'int', 'int'), 'int**'),
                      'span': DEFAULT_EXTENT}],
        'variable': [{'type': 'a',
                      'span': DEFAULT_EXTENT}],
    }
    eq__(sig_needles(fixture),
        [(('c-sig', '(int**, int, int) -> int**'), DEFAULT_EXTENT)])
