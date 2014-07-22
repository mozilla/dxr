from funcy import decorator, imap, tap
from nose import SkipTest
from nose.tools import eq_

from dxr.plugins.clang.condense import get_condensed
from dxr.plugins.utils import Extent, Position, FuncSig, Call

DEFAULT_LOC = ('x', Position(None, 0, 0))
DEFAULT_EXTENT = Extent(start=Position(0, 0, 0), end=Position(0, 0, 0))


@decorator
def csv_from_doc(call):
    csv = get_condensed('', (x.strip() for x in  (call._func.__doc__ or '').splitlines() if x.strip()))
    return call(csv)

@csv_from_doc
def test_smoke_test_csv(csv):
    pass

@csv_from_doc
def test_ref(csv):
    """
    ref,declloc,"x:0:0",loc,"x:0:0",kind,"function",extent,0:0
    ref,declloc,"x:0:0",loc,"x:0:0",kind,"variable",extent,0:0
    """
    eq_(csv['ref']['function'], [{'declloc': DEFAULT_LOC,
                                  'kind': 'function',
                                  'span': DEFAULT_EXTENT}])
    eq_(csv['ref']['variable'], [{'declloc': DEFAULT_LOC,
                                  'kind': 'variable',
                                  'span': DEFAULT_EXTENT}])
    
@csv_from_doc
def test_function(csv):
    """function,name,"comb",qualname,"comb(int **, int, int)",type,"int **",args,"(int **, int, int)",loc,"x:0:0",extent,0:0"""
    eq_(csv['function'][0], {
        'name': 'comb',
        'qualname': 'comb(int **, int, int)',
        'type': FuncSig(input=('int **', 'int', 'int'), output='int **'),
        'span': DEFAULT_EXTENT
    })

@csv_from_doc
def test_variable(csv):
    """variable,name,"a",qualname,"comb(int **, int, int)::a",loc,"x:0:0",type,"int **",scopename,"comb(int **, int, int)",scopeloc,"x:0:0",extent,0:0"""
    eq_(csv['variable'][0], {
        'name': 'a',
        'qualname': 'comb(int **, int, int)::a',
        'type': 'int **',
        'scope': {'loc': DEFAULT_LOC,
                  'name': 'comb(int **, int, int)'},
        'span': DEFAULT_EXTENT
    })

@csv_from_doc
def test_call(csv):
    """
    call,callername,"main()",callerloc,"x:0:0",calleename,"comb(int **, int, int)",calleeloc,"x:0:0",calltype,"static"
    call,callername,"main()",callerloc,"x:0:0",calleename,"comb(int **, int, int)",calleeloc,"x:0:0",calltype,"virtual"
    """
    eq_(csv['call'][0], Call(callee=('comb(int **, int, int)', DEFAULT_LOC),
                             caller=('main()', DEFAULT_LOC),
                             calltype='static'))

    eq_(csv['call'][1], Call(callee=('comb(int **, int, int)', DEFAULT_LOC),
                             caller=('main()', DEFAULT_LOC),
                             calltype='virtual'))


@csv_from_doc
def test_macro(csv):
    """
    macro,loc,"x:0:0",name,"X",args,"(x, y)",text,"x + y",extent,0:0
    macro,loc,"x:0:0",name,"X",text,"2",extent,0:0
    """
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


@csv_from_doc
def test_typedef(csv):
    """typedef,name,"x",qualname,"x",loc,"x:0:0",extent,0:0"""
    eq_(csv['typedef'][0], {
        'name': 'x',
        'qualname': 'x',
        'span': DEFAULT_EXTENT
    })

@csv_from_doc
def test_type(csv):
    """
    type,name,"foobar",qualname,"foobar",loc,"x:0:0",kind,"struct",extent,0:0
    type,name,"X",qualname,"X",loc,"x:0:0",kind,"class",extent,0:0
    """
    eq_(csv['type']['struct'][0], {
        'name': 'foobar',
        'qualname': 'foobar',
        'kind': 'struct',
        'span': DEFAULT_EXTENT
    })

    eq_(csv['type']['class'][0], {
        'name': 'X',
        'qualname': 'X',
        'kind': 'class',
        'span': DEFAULT_EXTENT
    })
    

@csv_from_doc
def test_impl(csv):
    """impl,tcname,"Y",tcloc,"x:0:0",tbname,"X",tbloc,"x:0:0",access,"public"""
    
    eq_(csv['impl'][0], {
        'tb': {'name': 'X', 'loc': DEFAULT_LOC},
        'tc': {'name': 'Y', 'loc': DEFAULT_LOC},
        'access': 'public'
    })

@csv_from_doc
def test_decldef(csv):
    """decldef,qualname,"Queue::Queue<T>(int)",declloc,"x:0:0",defloc,"x:0:0",kind,"function",extent,0:0"""
    eq_(csv['decldef']['function'][0], {
        'qualname': 'Queue::Queue<T>(int)',
        'declloc': DEFAULT_LOC,
        'defloc': DEFAULT_LOC,
        'kind': 'function',
        'extent': Extent(0, 0)
    })
    

@csv_from_doc
def test_warning(csv):
    """warning,loc,"x:0:0",msg,"hi",opt,"-oh-hi",extent,0:0"""
    eq_(csv['warning'][0], {'msg': 'hi', 'opt': '-oh-hi', 'span': DEFAULT_EXTENT})

@csv_from_doc
def test_namespace_alias(csv):
    """namespace_alias,name,"foo",qualname,"foo",loc,"x:0:0",extent,0:0"""
    eq_(csv['namespace_alias'][0], {
        'name': 'foo',
        'qualname': 'foo',
        'span': DEFAULT_EXTENT})

@csv_from_doc
def test_namespace(csv):
    """namespace,name,"x",qualname,"x",loc,"x:0:0",extent,0:0"""
    eq_(csv['namespace'][0], {
        'name': 'x',
        'qualname': 'x',
        'span': DEFAULT_EXTENT
    })

@csv_from_doc
def test_include(csv):
    """include,source_path,"foo",target_path,"bar",loc,"x:0:0",extent,0:0"""
    eq_(csv['include'][0], {
        'source_path': 'foo',
        'target_path': 'bar',
        'span': DEFAULT_EXTENT
    })
