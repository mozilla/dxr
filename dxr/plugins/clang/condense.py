"""Mirrors the intermediate representation of tern's condense output used by
the js plugin.

"""

import csv
from hashlib import sha1
from os import path
from glob import glob
from operator import itemgetter
from itertools import chain, izip

from networkx import DiGraph
from funcy import (walk, decorator, identity, select_keys, zipdict, merge,
                   imap, ifilter, group_by, compose, autocurry, is_mapping,
                   pluck)
from toposort import toposort_flatten

from dxr.plugins.utils import FuncSig, Position, Extent, Call


POSSIBLE_FIELDS = {'call', 'macro', 'function', 'name', 'variable', 'ref',
                   'type', 'impl', 'decldef', 'typedef', 'warning',
                   'namespace', 'namespace_alias', 'include'}


@decorator
def without(call, *keys):
    """Returns dictionary without the given keys"""
    return select_keys(lambda k: k not in keys, call())


@without('args')
def process_function(props):
    """Create !type: FuncSig based on args."""
    input_args = tuple(ifilter(
        bool, imap(str.lstrip, props['args'][1:-1].split(","))))
    props['type'] = FuncSig(input_args, props['type'])
    return props


@without('loc', 'extent')
def process_loc(props):
    """Create extent based on !loc and !extent."""
    _, row, col = props['loc'].split(':')
    start, end = props['extent'].split(':')
    props['span'] = Extent(Position(start, row, col), Position(end, row, col))
    return props


def _process_loc(locstring):
    if locstring is None:
        return None

    src, row, col = locstring.split(':')
    return src, Position(None, row, col)


def process_declloc(props):
    """Create Position based on declloc."""
    props['declloc'] = _process_loc(props['declloc'])
    return props


def process_call(props):
    """Group caller and callee for the call site."""
    return Call(
        (props['calleename'], _process_loc(props.get('calleeloc'))),
        (props.get('callername'), _process_loc(props.get('callerloc'))),
        props['calltype'])


def process_scope(props):
    """Group scopeloc and scopename into a scope field."""
    return group_loc_name('scope', props)


def group_loc_name(base, props):
    """Group the loc and name fields into a base field."""
    root = '{0}'.format(base)
    name, loc = '{0}name'.format(base), '{0}loc'.format(base)

    @without(name, loc)
    def _group_loc_name(props):
        src, row, col = props[loc].split(':')
        props[root] = {'loc': (src, Position(None, row, col)),
                       'name': props[name]}
        return props
    return _group_loc_name(props)

handlers = {
    'call': process_call,
    'function': process_function,
}


@autocurry
def process_fields(kind, fields):
    """Return new fields dict based on the current contents."""
    fields = handlers.get(kind, identity)(fields)

    if 'loc' in fields:
        fields = process_loc(fields)

    if 'scopeloc' in fields:
        fields = process_scope(fields)

    if 'declloc' in fields:
        fields = process_declloc(fields)

    return fields


def process((kind, vals)):
    """Process row from csv output."""
    return kind, map(compose(process_fields(kind), itemgetter(1)), vals)


@autocurry
def _get_condensed(fpath, csv_path):
    key = itemgetter(0)
    with open(csv_path, 'rb') as f:
        condensed = group_by(key, ((line[0], zipdict(line[1::2], line[2::2]))
                                   for line in csv.reader(f)))
    condensed = walk(process, condensed)
    condensed['name'] = fpath
    return condensed


def load_csv(csv_root, fpath):
    """Given a path to a build csv, return a dict representing the analysis."""
    csv_paths = glob("{0}.*.csv".format(
        path.join(csv_root, sha1(fpath).hexdigest())))

    return reduce(merge, imap(_get_condensed(fpath), csv_paths),
                  dict((key, []) for key in POSSIBLE_FIELDS))


def call_graph(condensed):
    """Create networkx DiGraph with edges representing funciton caller -> callee"""
    g = DiGraph()
    inherit = build_inhertitance(condensed)
    for call in condensed['call']:
        g.add_edge(call.caller, call.callee, attr=call)
        if call.calltype == 'virtual':
            # add children
            callee_qname, pos = call.callee
            if "::" in callee_qname:
                scope, func = callee_qname.split('::')
                for child in inherit[scope]:
                    child_qname = "{0}::{1}".format(child, func)
                    g.add_edge(call.caller, (child_qname, pos), attr=call)
    return g


def _relate((parent, children)):
    return parent, set((child['tcname']) for child in children)


def build_inhertitance(condensed):
    """Builds mapping class -> set of all descendants."""
    tree = walk(_relate, group_by(itemgetter('tbname'), condensed['impl']))
    tree.default_factory = set
    for node in toposort_flatten(tree):
        children = tree[node]
        for child in set(children):
            tree[node] |= tree[child]
    return tree


def symbols(condensed):
    """Return a dict, (symbol name) -> (dict of fields and metadata)."""
    for props in chain.from_iterable(condensed.values()):
        if is_mapping(props) and 'name' in props:
            yield props['name'], props


def functions(condensed):
    """Return an iterator of pairs (symbol, val) if symbol is a function."""
    funcs = condensed['function']
    return izip(pluck('name', funcs), funcs)
