"""Unit tests for clang plugin"""

from mock import MagicMock
from nose.tools import eq_
from funcy import first

from dxr.indexers import Extent, Position, FuncSig, Call
from dxr.plugins.clang.indexers import TreeToIndex, FileToIndex, kind_getter
from dxr.plugins.clang.needles import (
    callee_needles, caller_needles, child_needles, parent_needles,
    member_needles, sig_needles, overrides_needles, overridden_needles)

from dxr.plugins.clang.condense import (get_condensed, build_inheritance,
                                        call_graph, c_type_sig)


DEFAULT_LOC = ('x', Position(None, 0, 0))
DEFAULT_EXTENT = Extent(start=Position(0, 0, 0), end=Position(0, 0, 0))
CALL_EXTENT = Extent(start=Position(None, 0, 0), end=Position(None, 0, 0))


def get_csv(csv_str):
    return get_condensed(x.strip() for x in csv_str.splitlines()
                         if x.strip())


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


def test_function():
    csv = get_csv("""
        function,name,"comb",qualname,"comb(int **, int, int)",type,"int **",args,"(int **, int, int)",loc,"x:0:0",extent,0:0
        function,name,"op",qualname,"add::op()",type,"void",args,"()",loc,"x:0:0",scopename,"add",scopeloc,"x:0:0",extent,0:0,overridename,"base::op()",overrideloc,"x:0:0"
    """)
    eq_(csv['function'][0], {
        'name': 'comb',
        'qualname': 'comb(int **, int, int)',
        'type': FuncSig(('int**', 'int', 'int'), 'int**'),
        'span': DEFAULT_EXTENT
    })
    eq_(csv['function'][1], {
        'name': 'op',
        'qualname': 'add::op()',
        'type': FuncSig(inputs=tuple(['void']), output='void'),
        'span': DEFAULT_EXTENT,
        'scope': {
            'name': 'add',
            'loc': DEFAULT_LOC
        },
        'override': {
            'name': 'base::op()',
            'loc': DEFAULT_LOC,
        }
    })


def test_variable():
    csv = get_csv("""
        variable,name,"a",qualname,"comb(int **, int, int)::a",loc,"x:0:0",type,"int **",scopename,"comb(int **, int, int)",scopeloc,"x:0:0",extent,0:0
    """)
    eq_(csv['variable'][0], {
        'name': 'a',
        'qualname': 'comb(int **, int, int)::a',
        'type': 'int **',
        'scope': {'loc': DEFAULT_LOC,
                  'name': 'comb(int **, int, int)'},
        'span': DEFAULT_EXTENT
    })


def test_call():
    csv = get_csv("""
        call,callername,"main()",callerloc,"x:0:0",calleename,"comb(int **, int, int)",calleeloc,"x:0:0",calltype,"static"
        call,callername,"main()",callerloc,"x:0:0",calleename,"comb(int **, int, int)",calleeloc,"x:0:0",calltype,"virtual"
    """)
    eq_(csv['call'][0], Call(callee=('comb(int **, int, int)', CALL_EXTENT),
                             caller=('main()', CALL_EXTENT),
                             calltype='static'))
    eq_(csv['call'][1], Call(callee=('comb(int **, int, int)', CALL_EXTENT),
                             caller=('main()', CALL_EXTENT),
                             calltype='virtual'))


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
    inherit = build_inheritance(csv)
    eq_(inherit, INHERIT)


def test_callgraph():
    """Test that virtual call expands into 4 different calls
    There are also the 2 static calls.

    """

    csv = get_csv("""
        impl,tcname,"Y",tcloc,"x:0:0",tbname,"X",tbloc,"x:0:0",access,"public"
        impl,tcname,"Z",tcloc,"x:0:0",tbname,"X",tbloc,"x:0:0",access,"public"
        impl,tcname,"W",tcloc,"x:0:0",tbname,"Z",tbloc,"x:0:0",access,"public"
        impl,tcname,"W",tcloc,"x:0:0",tbname,"Y",tbloc,"x:0:0",access,"public"
        call,callername,"foo2()",callerloc,"x:0:0",calleename,"X::X()",calleeloc,"x:0:0",calltype,"static"
        call,callername,"foo2()",callerloc,"x:0:0",calleename,"X::foo()",calleeloc,"x:0:0",calltype,"virtual"
        call,callername,"bar()",callerloc,"x:0:0",calleename,"foo2()",calleeloc,"x:0:0",calltype,"static"
    """)
    g = call_graph(csv)
    eq_(len(set(g.keys())), 6)


def smoke_test_tree():
    TreeToIndex('test')


def test_FileToIndex():
    FileToIndex('', '', MagicMock(), {})


def eq__(l1, l2):
    eq_(list(l1), list(l2))


def test_call_needles():
    fixture = {
        'call': [
            Call(callee=('comb(int **, int, int)', CALL_EXTENT),
                 caller=('main()', CALL_EXTENT),
                 calltype='static'),
            Call(callee=('comb(int **, int, int)', CALL_EXTENT),
                 caller=('main()', CALL_EXTENT),
                 calltype='virtual')
        ]
    }
    g = call_graph(fixture, {})
    eq__(callee_needles(g),
         [(('c-callee', 'comb(int **, int, int)'), CALL_EXTENT),
          (('c-callee', 'comb(int **, int, int)'), CALL_EXTENT)])

    eq__(caller_needles(g),
         [(('c-called-by', 'main()'), CALL_EXTENT),
          (('c-called-by', 'main()'), CALL_EXTENT)])


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


def test_member_needles():
    fixture = {
        'foo': [{'scope': {'name': 'A'}, 'span': DEFAULT_EXTENT}]
    }
    eq__(member_needles(fixture), [(('c-member', 'A'), DEFAULT_EXTENT)])


def test_override_needles():
    fixture = {
        'function': [{'override': {'name': 'x', 'span': DEFAULT_EXTENT}}],
    }
    eq__(overrides_needles({
        'function': [{'override': {'name': 'x'}, 'span': DEFAULT_EXTENT}],
    }), [(('c-overrides', 'x'), DEFAULT_EXTENT)])
    eq__(overridden_needles({
        'function': [{'override': {'name': 'x', 'span': DEFAULT_EXTENT}}],
    }), [(('c-overridden', 'x'), DEFAULT_EXTENT)])


def test_kind_getter():
    csv = get_csv("""
    ref,declloc,"x:0:0",loc,"x:0:0",kind,"function",extent,0:0
    ref,declloc,"x:0:0",loc,"x:0:0",kind,"variable",extent,0:0
    """)
    eq__(first(kind_getter('ref', 'function')(csv))['kind'], 'function')
    eq__(first(kind_getter('ref', 'variable')(csv))['kind'], 'variable')
