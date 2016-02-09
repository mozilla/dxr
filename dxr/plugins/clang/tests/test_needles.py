from nose.tools import eq_

from dxr.plugins.clang.needles import _walk_graph


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
