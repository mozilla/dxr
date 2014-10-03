from nose.tools import eq_

from dxr.plugins.clang.condense import c_type_sig
from dxr.indexers import FuncSig


def test_type_structure():
    sig = c_type_sig(["a", "b"], "o")
    eq_(len(sig.inputs), 2)


def test_boxing():
    eq_(c_type_sig(["int **"], "int*"), FuncSig(("int**",), ("int*")))


def test_method():
    eq_(c_type_sig(["a"], "b", method="A"), FuncSig(("A", "a"), "b"))


def test_void_elimination():
    eq_(c_type_sig(["void"], "b", method="A"), FuncSig(("A",), "b"))


def test_void_alias():
    eq_(c_type_sig([], 'a'), FuncSig(('void',), 'a'))


def test_type_classes():
    eq_(c_type_sig(['bool'], 'Q<T>'), FuncSig(('bool',), 'Q<T>'))


def test_str_rep():
    eq_(str(c_type_sig(['bool', 'int'], 'Q<T>', method='Q<T>')),
        "(Q<T>, bool, int) -> Q<T>")

