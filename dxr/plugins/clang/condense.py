"""Mirrors the intermediate representation of tern's condense output used by
the js plugin.

"""

import csv
from hashlib import sha1
from os import path
from glob import glob
from operator import itemgetter
from itertools import chain, izip

from funcy import (walk, decorator, identity, select_keys, zipdict, merge,
                   imap, ifilter, group_by, compose, autocurry, is_mapping,
                   pluck, first, remove)
from toposort import toposort_flatten

from dxr.plugins.utils import FuncSig, Position, Extent, Call


POSSIBLE_FIELDS = set(['call', 'macro', 'function', 'variable', 'ref',
                       'type', 'impl', 'decldef', 'typedef', 'warning',
                       'namespace', 'namespace_alias', 'include'])


def c_type_sig(inputs, output, method=None):
    """Return FuncSig based on C style input, output, and method."""
    inputs = remove(lambda x: x == "void", inputs)  # Void Elimination

    inputs = map(lambda x: x.replace(' ', ''), inputs)  # Space Elimination
    output = output.replace(' ', '')

    if method is not None:  # Implicit first argument
        inputs = [method] + inputs

    if len(inputs) == 0:  # Expand no inputs to a single void input
        inputs = ["void"]

    return FuncSig(tuple(inputs), output)


@decorator
def without(call, *keys):
    """Return dictionary without the given keys"""
    return select_keys(lambda k: k not in keys, call())


@without('args')
def process_function(props):
    """Return FuncSig based on args."""
    input_args = tuple(ifilter(
        bool, imap(str.lstrip, props['args'][1:-1].split(","))))
    props['type'] = c_type_sig(input_args, props['type'])
    return props


@without('loc', 'extent')
def process_loc(props):
    """Return extent based on loc and extent."""
    row, col = map(int, props['loc'].split(':')[1:])
    start, end = map(int, props['extent'].split(':'))
    props['span'] = Extent(Position(start, row, col), Position(end, row, col))
    return props


def _process_loc(locstring):
    """Analysis locstring for src and Position."""
    if locstring is None:
        return None

    src, row, col = locstring.split(':')
    return src, Position(None, int(row), int(col))


def process_declloc(props):
    """Return Position based on declloc."""
    props['declloc'] = _process_loc(props['declloc'])
    return props


def process_defloc(props):
    """Return Position based on defloc and extent."""
    props['defloc'] = _process_loc(props['defloc'])
    props['extent'] = Extent(*map(int, props['extent'].split(':')))
    return props


def process_impl(props):
    props = group_loc_name('tc', props)
    return group_loc_name('tb', props)


def process_call(props):
    """Group caller and callee for the call site."""
    callee_pos = _process_loc(props.get('calleeloc'))[1]
    caller_pos = _process_loc(props.get('callerloc'))[1]
    return Call(
        (props['calleename'], Extent(callee_pos, callee_pos)),
        (props.get('callername'), Extent(caller_pos, caller_pos)),
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
        props[root] = {'loc': (src, Position(None, int(row), int(col))),
                       'name': props[name]}
        return props
    return _group_loc_name(props)

handlers = {
    'call': process_call,
    'function': process_function,
    'impl': process_impl
}


@autocurry
def process_fields(kind, fields):
    """Return new fields dict based on the current contents.

    :arg kind: the ast node type specified by the csv file.

    """
    fields = handlers.get(kind, identity)(fields)

    if 'loc' in fields:
        fields = process_loc(fields)

    if 'scopeloc' in fields:
        fields = process_scope(fields)

    if 'declloc' in fields:
        fields = process_declloc(fields)

    if 'defloc' in fields:
        fields = process_defloc(fields)

    return fields


def process((kind, vals)):
    """Process row from csv output."""
    mapping = map(compose(process_fields(kind), itemgetter(1)), vals)
    if 'kind' in first(mapping):
        mapping = group_by(itemgetter('kind'), mapping)
    return kind, mapping


def get_condensed(lines, only_impl=False):
    """Return condensed analysis of CSV files."""
    key = itemgetter(0)
    pred = lambda line: not only_impl or line[0] == 'impl'
    condensed = group_by(key, ((line[0], zipdict(line[1::2], line[2::2]))
                               for line in csv.reader(lines) if pred(line)))
    condensed = walk(process, condensed)
    return condensed


@autocurry
def _load_csv(fpath, csv_path, only_impl=False):
    """Open CSV_PATH and return the output of get_condensed based on csv."""
    with open(csv_path, 'rb') as f:
        return get_condensed(f, only_impl)


def load_csv(csv_root, fpath=None, only_impl=False):
    """Given a path to a build csv, return a dict representing the analysis."""
    hashed_fname = '*' if fpath is None else sha1(fpath).hexdigest()
    csv_paths = glob('{0}.*.csv'.format(path.join(csv_root, hashed_fname)))

    return reduce(merge, imap(_load_csv(fpath, only_impl=only_impl), csv_paths),
                  dict((key, []) for key in POSSIBLE_FIELDS))


def call_graph(condensed, inherit=None):
    """Return DiGraph with edges representing function caller -> callee."""
    g = {}
    if inherit is None:
        inherit = build_inheritance(condensed)

    for call in condensed['call']:
        g[call] = call
        if call.calltype == 'virtual':
            # add children
            callee_qname, pos = call.callee
            if '::' in callee_qname:
                scope, func = callee_qname.split('::')
                for child in inherit[scope]:
                    child_qname = "{0}::{1}".format(child, func)
                    g[(call.caller, (child_qname, pos), 'virtual')] = call
    return g


def _relate((parent, children)):
    return parent, set((child['tc']['name']) for child in children)


def build_inheritance(condensed):
    """Builds mapping class -> set of all descendants."""
    get_tbname = lambda x: x['tb']['name']  # tb are parents, tc are children
    tree = walk(_relate, group_by(get_tbname, condensed['impl']))
    tree.default_factory = set
    for node in toposort_flatten(tree):
        children = tree[node]
        for child in set(children):
            tree[node] |= tree[child]
    return tree
