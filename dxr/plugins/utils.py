"""Some common utilities used by plugins but _not_ required by the API"""

from collections import namedtuple

from funcy import flatten
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

from dxr.plugins import LINE

Extent = namedtuple('Extent', ['start', 'end'])
# Note that if offset is a Maybe Int, if not present it's None
Position = namedtuple('Position', ['offset', 'row', 'col'])
Call = namedtuple('Call', ['callee', 'caller', 'calltype'])


class FuncSig(namedtuple('FuncSig', ['inputs', 'output'])):
    def __str__(self):
        return encode('{0} -> {1}'.format(
            tuple(self.inputs), self.output).replace("'", '').replace('"', ''))


def _process_ctype(type_):
    return type_


TYPE_STR_GRAMMAR = Grammar(r"""
    start = _ "(" _ types _ ")" _ "->" _ type
    types = type ((_ "," _ type)?)+
    type = ident _ ("<" _ params _ ">" )? _ stars?
    ident = ~r"[\w\$_]+"
    stars = ~r"\*+"
    params = ident ((_ "," _ ident)?)+
    _ = ~r"\s*"
""")


class TypeStrVisitor(NodeVisitor):
    def visit_start(self, _, (_1, _2, _3, inputs, _4, _5, _6, _7, _8, output)):
        return ";".join(flatten(inputs + output))

    def visit_type(self, _, (ident, _1, params, _3, stars)):
        return [ident, params, stars]

    def visit_ident(self, node, _):
        return node.text

    def visit_stars(self, node, _):
        return list(node.text)

    def visit_types(self, _, (type_, type_list)):
        return type_ + type_list

    def visit_params(self, _, (param, param_list)):
        return [param] + param_list

    def generic_visit(self, _, children):
        return children


def encode(query):
    """Encode type search query for elastic search indexing."""
    return TypeStrVisitor().visit(TYPE_STR_GRAMMAR['start'].parse(query))


def is_function((_, obj)):
    if '!type' not in obj:
        return False
    type_ = obj['!type']
    return hasattr(type_, 'input') and hasattr(type_, 'output')
