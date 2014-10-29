"""Unit tests for clang plugin

Most of these have been deleted in favor of integration tests elsewhere, and
we can probably go further in that direction.

"""
import csv
from itertools import ifilter
from StringIO import StringIO

from funcy import first
from nose.tools import eq_

from dxr.indexers import Extent, Position, FuncSig
from dxr.plugins.clang.condense import (condense, build_inheritance,                                        c_type_sig, DISPATCH_TABLE)
from dxr.plugins.clang.indexers import kind_getter
from dxr.plugins.clang.needles import (child_needles, parent_needles,
    member_needles, sig_needles, overrides_needles, overridden_needles)


DEFAULT_LOC = ('x', Position(None, 0, 0))
DEFAULT_EXTENT = Extent(start=Position(0, 0, 0), end=Position(0, 0, 0))
CALL_EXTENT = Extent(start=Position(None, 0, 0), end=Position(None, 0, 0))


def get_csv(csv_str):
    return condense(csv.reader(StringIO('\n'.join(ifilter(None, (x.strip() for x in csv_str.splitlines()))))),
                    DISPATCH_TABLE)


def test_smoke_test_csv():
    get_csv('')


def test_ref():
    csv = get_csv("""
        ref,declloc,"x:0:0",loc,"x:0:0",kind,"function",qualname,"another_file()",extent,0:0
        ref,declloc,"x:0:0",loc,"x:0:0",kind,"variable",qualname,"main(int, char **)::a",extent,0:0
    """)
    eq_(csv['ref'][0], {'declloc': DEFAULT_LOC,
                        'kind': 'function',
                        'span': DEFAULT_EXTENT,
                        'qualname': 'another_file()'})
    eq_(csv['ref'][1], {'declloc': DEFAULT_LOC,
                        'kind': 'variable',
                        'span': DEFAULT_EXTENT,
                        'qualname': 'main(int, char **)::a'})


def test_macro():
    csv = get_csv("""
        macro,loc,"x:0:0",name,"X",args,"(x, y)",text,"x + y",extent,0:0
        macro,loc,"x:0:0",name,"X",text,"2",extent,0:0
    """)
    eq_(csv['macro'][0], {
        'name': 'X',
        'args': '(x, y)',
        'text': 'x + y',
        'span': DEFAULT_EXTENT
    })
    eq_(csv['macro'][1], {
        'name': 'X',
        'text': '2',
        'span': DEFAULT_EXTENT
    })


def test_typedef():
    csv = get_csv("""
        typedef,name,"x",qualname,"x",loc,"x:0:0",extent,0:0
    """)
    eq_(csv['typedef'][0], {
        'name': 'x',
        'qualname': 'x',
        'span': DEFAULT_EXTENT
    })


def test_type():
    csv = get_csv("""
        type,name,"foobar",qualname,"foobar",loc,"x:0:0",kind,"struct",extent,0:0
        type,name,"X",qualname,"X",loc,"x:0:0",kind,"class",extent,0:0
    """)
    eq_(csv['type'][0], {
        'name': 'foobar',
        'qualname': 'foobar',
        'kind': 'struct',
        'span': DEFAULT_EXTENT
    })
    eq_(csv['type'][1], {
        'name': 'X',
        'qualname': 'X',
        'kind': 'class',
        'span': DEFAULT_EXTENT
    })


def test_impl():
    csv = get_csv("""
        impl,tcname,"Y",tcloc,"x:0:0",tbname,"X",tbloc,"x:0:0",access,"public"
    """)
    eq_(csv['impl'][0], {
        'tb': {'name': 'X', 'loc': DEFAULT_LOC},
        'tc': {'name': 'Y', 'loc': DEFAULT_LOC},
        'access': 'public'
    })


def test_decldef():
    csv = get_csv("""
        decldef,qualname,"Queue::Queue<T>(int)",loc,"x:0:0",defloc,"x:0:0",kind,"function",extent,0:0
    """)
    eq_(csv['decldef'][0], {
        'qualname': 'Queue::Queue<T>(int)',
        'span': DEFAULT_EXTENT,
        'defloc': DEFAULT_LOC,
        'kind': 'function'
    })


def test_warning():
    csv = get_csv("""
        warning,loc,"x:0:0",msg,"hi",opt,"-oh-hi",extent,0:0
    """)
    eq_(csv['warning'][0],
        {'msg': 'hi', 'opt': '-oh-hi', 'span': DEFAULT_EXTENT})


def test_namespace_alias():
    csv = get_csv("""
        namespace_alias,name,"foo",qualname,"foo",loc,"x:0:0",extent,0:0
    """)
    eq_(csv['namespace_alias'][0], {
        'name': 'foo',
        'qualname': 'foo',
        'span': DEFAULT_EXTENT
    })


def test_namespace():
    csv = get_csv("""
        namespace,name,"x",qualname,"x",loc,"x:0:0",extent,0:0
    """)
    eq_(csv['namespace'][0], {
        'name': 'x',
        'qualname': 'x',
        'span': DEFAULT_EXTENT
    })


def test_include():
    csv = get_csv("""
        include,source_path,"foo",target_path,"bar",loc,"x:0:0",extent,0:0
    """)
    eq_(csv['include'][0], {
        'source_path': 'foo',
        'target_path': 'bar',
        'span': DEFAULT_EXTENT
    })


INHERIT = {'X': {'Y', 'Z', 'W'},
           'Y': {'W'},
           'Z': {'W'},
           'W': set()}


def test_inheritance():
    csv = get_csv("""
        impl,tcname,"Y",tcloc,"main.cpp:10:7",tbname,"X",tbloc,"main.cpp:9:7",access,"public"
        impl,tcname,"Z",tcloc,"main.cpp:11:7",tbname,"X",tbloc,"main.cpp:9:7",access,"public"
        impl,tcname,"W",tcloc,"main.cpp:12:7",tbname,"Z",tbloc,"main.cpp:11:7",access,"public"
        impl,tcname,"W",tcloc,"main.cpp:12:7",tbname,"Y",tbloc,"main.cpp:10:7",access,"public"
    """)
    inherit = build_inheritance(csv['impl'])
    eq_(inherit, INHERIT)


def eq__(l1, l2):
    eq_(list(l1), list(l2))


def test_inherit_needles():
    csv = get_csv("""
        impl,tcname,"Y",tcloc,"x:0:0",tbname,"X",tbloc,"x:0:0",access,"public"
        impl,tcname,"Z",tcloc,"x:0:0",tbname,"X",tbloc,"x:0:0",access,"public"
        impl,tcname,"W",tcloc,"x:0:0",tbname,"Z",tbloc,"x:0:0",access,"public"
        impl,tcname,"W",tcloc,"x:0:0",tbname,"Y",tbloc,"x:0:0",access,"public"
        type,name,"X",qualname,"X",loc,"x:0:0",kind,"class",extent,0:0
        type,name,"Y",qualname,"Y",loc,"x:0:0",kind,"class",extent,0:0
        type,name,"W",qualname,"W",loc,"x:0:0",kind,"class",extent,0:0
        type,name,"Z",qualname,"Z",loc,"x:0:0",kind,"class",extent,0:0
    """)
    c_needles = [(('c-child', 'Y'), DEFAULT_EXTENT),
                 (('c-child', 'Z'), DEFAULT_EXTENT),
                 (('c-child', 'W'), DEFAULT_EXTENT),
                 (('c-child', 'W'), DEFAULT_EXTENT),
                 (('c-child', 'W'), DEFAULT_EXTENT)]

    eq_(len(list(child_needles(csv, INHERIT))), len(c_needles))
    eq_(set(child_needles(csv, INHERIT)), set(c_needles))

    p_needles = [(('c-parent', 'X'), DEFAULT_EXTENT),
                 (('c-parent', 'X'), DEFAULT_EXTENT),
                 (('c-parent', 'Y'), DEFAULT_EXTENT),
                 (('c-parent', 'X'), DEFAULT_EXTENT),
                 (('c-parent', 'Z'), DEFAULT_EXTENT)]
    eq_(len(list(parent_needles(csv, INHERIT))), len(p_needles))
    eq_(set(parent_needles(csv, INHERIT)), set(p_needles))


def test_sig_needles():
    fixture = {
        'function': [{'type': FuncSig(('int**', 'int', 'int'), 'int**'),
                      'span': DEFAULT_EXTENT}],
        'variable': [{'type': 'a',
                      'span': DEFAULT_EXTENT}],
    }
    eq__(sig_needles(fixture),
        [(('c-sig', '(int**, int, int) -> int**'), DEFAULT_EXTENT)])


def test_kind_getter():
    csv = get_csv("""
    ref,declloc,"x:0:0",loc,"x:0:0",kind,"function",extent,0:0
    ref,declloc,"x:0:0",loc,"x:0:0",kind,"variable",extent,0:0
    """)
    eq__(first(kind_getter('ref', 'function')(csv))['kind'], 'function')
    eq__(first(kind_getter('ref', 'variable')(csv))['kind'], 'variable')
