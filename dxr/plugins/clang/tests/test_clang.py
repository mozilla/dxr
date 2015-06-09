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


DEFAULT_EXTENT = Extent(start=Position(0, 0), end=Position(0, 0))


def condense_csv(csv_str):
    return condense(csv.reader(StringIO('\n'.join(ifilter(None, (x.strip() for x in csv_str.splitlines()))))),
                    DISPATCH_TABLE)


def test_smoke_test_csv():
    condense_csv('')


def test_sig_needles():
    fixture = {
        'function': [{'type': FuncSig(('int**', 'int', 'int'), 'int**'),
                      'span': DEFAULT_EXTENT}],
        'variable': [{'type': 'a',
                      'span': DEFAULT_EXTENT}],
    }
    eq_(list(sig_needles(fixture)),
        [(('c-sig', '(int**, int, int) -> int**'), DEFAULT_EXTENT)])


def test_duplicate_collapsing():
    """Duplicate condensed data should be filtered out.

    Duplicates CSV lines are encountered when the clang plugin emits multiple
    CSVs for a single source file, which happens when they have different
    contents at different points during compilation (due to preprocessor
    directives?).

    """
    line = '''variable,name,"mAtkObject",qualname,"mozilla::a11y::AccessibleWrap::mAtkObject",loc,"accessible/atk/AccessibleWrap.h:83:13",locend,"accessible/atk/AccessibleWrap.h:83:23",type,"AtkObject *",scopename,"AccessibleWrap",scopequalname,"mozilla::a11y::AccessibleWrap"'''
    eq_(condense_csv(line + '\n' + line),
        condense_csv(line))
