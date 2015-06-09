"""Module to processing the output of Tern's condense command.'"""

import json
import subprocess
from functools import wraps
from itertools import chain, imap

from parsimonious import Grammar, NodeVisitor

import requests

from dxr.indexers import FuncSig, Extent, Position, symbols, functions


class ExtentVisitor(NodeVisitor):
    def visit_num(self, node, _):
        return int(node.text)

    def visit_pos(self, _, (_0, row, _1, col, _2)):
        return (row, col)

    def visit_extent(self, _, (off1, (row1, col1), __, off2, (row2, col2))):
        return Extent(Position(off1, row1, col1), Position(off2, row2, col2))

    def generic_visit(self, _, __):
        return None

extent_grammar = Grammar(r"""
    extent = num pos "-" num pos
    pos = "[" num ":" num "]"
    num = ~r"\d+"
""")


class ValueVisitor(NodeVisitor):
    def visit_val(self, node, (val,)):
        return val if val else node.text

    def visit_list(self, _, (_1, type_, _2)):
        return "[" + type_ + "]"

    def visittype_(self, node, (child,)):
        return child if child else node.text

    def visit_func(self, _, (_1, _2, args, _3, type_)):
        if type_ == []:
            type_ = [None]
        return FuncSig(args, type_[0])

    def visit_arg(self, _, (name, type_, _2)):
        return (name, type_[0] if type_ else None)

    def visit_argtype_(self, node, (_, val)):
        return val

    def visit_output(self, _, (_1, val)):
        return val

    def visit_name(self, node, _):
        return node.text

    def visit_qname(self, node, _):
        return node.text

    def generic_visit(self, _, children):
        return children


def create_handler(grammar, visitor):
    """Factory for creating a 'handler' for a given !key."""
    visitor_inst = visitor()
    return lambda x: visitor_inst.visit(grammar.parse(x))


value_grammar = Grammar(r"""
    val = func / list / qname / name
    qname = name ":" (qname / name)
    func = "fn" "(" args ")" output?
    output = " -> " val
    args = arg*
    arg = name arg_type? ", "?
    arg_type = (": " val)
    name = ~r"[+?!\.\w<>]+"
    list = "[" val "]"
""")


handlers = {
    '!name': str,
    '!url': str,
    '!doc': str,
    '!span': create_handler(extent_grammar, ExtentVisitor),
    '!type': create_handler(value_grammar, ValueVisitor),
    '!define': str,
    '!effects': str,
    '!proto': str,
    '!stdProto': str,
}


def hook(d):
    """Hook for json.loads, dispatches function based on handlers."""
    d2 = dict(d)
    for key, val in d.iteritems():
        if key.startswith('!'):
            d2[key] = handlers[key](val)
    return d2


# Not in Python 2.6 :(
def check_output(*popenargs, **kwargs):
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    return output


def get_condensed(fpath, condense_path):
    """Return dictionary from ternjs' condensed output."""
    condensed = check_output([condense_path, fpath])
    return json.loads(condensed, object_hook=hook)


def _properties((name, obj)):
    if not hasattr(obj, 'items'):
        return []
    return ((name, k, obj['!span']) for k in obj.iterkeys()
            if not k.startswith('!'))


def properties(condensed):
    """Return a list of pairs [(object name, property)]"""
    return chain.from_iterable(imap(_properties, symbols(condensed)))


def tern_request(func):
    """Make a request to the tern server based on return value of func."""
    @wraps
    def _tern_request(address, *args, **kwargs):
        req = requests.post(address, json.dumps(func(*args, **kwargs)))
        return req.json()
    return _tern_request


@tern_request
def register_file(condensed):
    name = condensed['!name']
    with open(name, 'r') as f:
        return {'files': [
            {'type': 'full',
             'name': name,
             'text': ''.join(f.readlines())}]}


@tern_request
def list_files():
    return {'query': {'type': 'files'}}


@tern_request
def get_ref(condensed, extent):
    return {'query': {'type': 'refs',
                      'file': condensed['!name'],
                      'start': extent.start.offset,
                      'end': extent.end.offset}}


def refs(address, condensed, extents):
    return (get_ref(address, condensed, extent) for extent in extents)


def call_sites(address, condensed):
    """Return all callsites."""
    extents = (func['!span'] for _, func in functions(condensed))
    return refs(address, condensed, extents)
