from collections import namedtuple
from itertools import permutations, ifilter
from operator import itemgetter
from functools import partial

from mock import MagicMock
from nose import SkipTest
from nose.tools import eq_

from dxr.plugins.clang import ClangTreeToIndex


def smoke_test():
    c = ClangTreeToIndex('test')


CORRECT_ORDER = [('environment', [{}]), ('pre_build', []), ('post_build', []),
                 ('file_to_index', ['foo', 'bar'])]


def check_order(order):
    c = ClangTreeToIndex(MagicMock())
    for cmd, args in order:
        getattr(c, cmd)(*args)


def check_incorrect_order(order):
    try:
        check_order(order)
        assert False
    except RuntimeError:
        pass


def correct_order_test():
    check_order(CORRECT_ORDER)

    
def incorrect_order_tests():
    only_cmds = partial(map, itemgetter(0))
    for order in permutations(CORRECT_ORDER):
        if only_cmds(order) == only_cmds(CORRECT_ORDER):
            continue
        yield check_incorrect_order, order


def test_FileToIndex():
    pass
