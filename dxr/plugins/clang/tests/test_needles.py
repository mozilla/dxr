from nose.tools import eq_

from dxr.indexers import Extent, Position, FuncSig
from dxr.plugins.clang.needles import _walk_graph, sig_needles


def test_sig_needles():
    dummy_extent = Extent(start=Position(0, 0), end=Position(0, 0))
    fixture = {
        'function': [{'type': FuncSig(('int**', 'int', 'int'), 'int**'),
                      'span': dummy_extent}],
        'variable': [{'type': 'a',
                      'span': dummy_extent}],
    }
    eq_(list(sig_needles(fixture)),
        [(('c-sig', '(int**, int, int) -> int**'), dummy_extent)])


def test_graph_walking_cycles():
    """Make sure _walk_graph() doesn't get stuck in cycles."""
    graph = {'A': [('B', 'b')],
             'B': [('C', 'c')],
             'C': [('A', 'a')]}
    eq_(set(_walk_graph(graph, 'A', set(['A']))),
        set([('B', 'b'), ('C', 'c')]))

def test_graph_walking_dupes():
    """Make sure _walk_graph() doesn't emit duplicates."""
    graph = {'A': [('B', 'b'), ('C', 'c')],
             'B': [('D', 'd')],
             'C': [('D', 'd')]}
    eq_(set(_walk_graph(graph, 'A', set(['A']))),
        set([('B', 'b'), ('C', 'c'), ('D', 'd')]))
