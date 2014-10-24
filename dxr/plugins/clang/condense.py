"""Representation of a compiler-emitted CSV as a hash

Mirrors the intermediate representation of tern's condense output used by
the js plugin. [Actually, has diverged somewhat. There may not be a good
reason to keep this IR.]

"""
import csv
from hashlib import sha1
from os import path
from glob import glob
from operator import itemgetter

from funcy import (walk, decorator, identity, select_keys, zipdict, merge,
                   imap, ifilter, group_by, compose, autocurry, is_mapping,
                   pluck, first, remove)
from toposort import toposort_flatten

from dxr.indexers import FuncSig, Position, Extent, Call


class UselessLine(Exception):
    """A CSV line isn't suitable for getting anything useful out of."""


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
    # Compute FuncSig based on args:
    input_args = tuple(ifilter(
        bool, imap(str.lstrip, props['args'][1:-1].split(","))))
    props['type'] = c_type_sig(input_args, props['type'])

    # Deal with overrides:
    if 'overrideloc' in props:
        props['overrideloc'] = _process_loc(props['overrideloc'])

    return props


@without('loc', 'extent')
def process_loc(props):
    """Return extent based on loc and extent."""
    if 'extent' not in props:
        # This happens with some macros which call other macros, like this:
        #   #define ID2(x) (x)
        #   #define ID(x) ID2(x)
        # In the second line, ID2 will get a macro ref line, but it will lack
        # an extent because the SourceLocation of ID2 will not be .isValid().
        # We never got that right, even in the SQLite implementation.
        raise UselessLine('Found a line with "loc" but without "extent".')

    row, col = map(int, props['loc'].split(':')[1:])
    start, end = map(int, props['extent'].split(':'))

    # TODO: This assumes the extent doesn't span lines. If it did, row would
    # have to change sometimes. Is this a problem, or do all extents pulled
    # out of CSVs stay each within one line? If they don't, we'll need to pass
    # the file text in here or, more easily and efficiently, improve the
    # compiler plugin.
    props['span'] = Extent(Position(start, row, col),
                           Position(end, row, col + end - start))

    return props


def _process_loc(locstring):
    """Turn a path:row:col string into (path, Position)."""
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
    return props


def process_impl(props):
    """Group tc and tb fields in impl field."""
    props = group_loc_name('tc', props)
    return group_loc_name('tb', props)


@without('callloc', 'calllocend')
def process_call(props):
    # This is a pilot test of outputting row/col for both start and end from
    # the compiler plugin. It lets us construct reliable Extents, with no
    # assumption that they don't span lines.
    _, call_start = _process_loc(props['callloc'])
    _, (_, call_end_row, call_end_col) = _process_loc(props['calllocend'])
    if call_end_col > call_start.col + 1:
        # The span coming out of the compiler includes the left paren. Stop that.
        call_end_col -= 1
    props['span'] = Extent(call_start,
                           Position(offset=None, row=call_end_row, col=call_end_col))
    props['calleeloc'] = _process_loc(props['calleeloc'])  # for Jump To
    return props


def process_scope(props):
    """Group scopeloc and scopename into a scope field."""
    return group_loc_name('scope', props)


def process_override(props):
    """Group overrideloc and overridename into a override field."""
    return group_loc_name('override', props)


def group_loc_name(base, props):
    """Group the loc and name fields into a base field."""
    name, loc = '{0}name'.format(base), '{0}loc'.format(base)

    @without(name, loc)
    def _group_loc_name(props):
        src, row, col = props[loc].split(':')
        props[base] = {'loc': (src, Position(None, int(row), int(col))),
                       'name': props[name]}
        return props
    return _group_loc_name(props)


HANDLERS = {
    'call': process_call,
    'function': process_function,
    'impl': process_impl
}


def process_fields(kind, fields):
    """Return new fields dict based on a single row of a CSV file.

    Return {} if this row is useless and should be ignored.

    :arg kind: the ast node type specified by the csv file.

    """
    fields = HANDLERS.get(kind, identity)(fields)

    try:
        if 'loc' in fields:
            fields = process_loc(fields)

        if 'scopeloc' in fields:
            fields = process_scope(fields)

        if 'declloc' in fields:
            fields = process_declloc(fields)

        if 'defloc' in fields:
            fields = process_defloc(fields)
    except UselessLine:
        return {}

    return fields


def process((kind, vals)):
    """Process all rows of a given kind from a CSV file.

    :arg kind: The (consistent) value of the first field of the rows
    :arg vals: An iterable of tuples representing the contents of each row::

        (kind, {dict of remaining fields as key/value pairs})

    """
    mapping = filter(None, imap(lambda v: process_fields(kind, v[1]), vals))
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
def _load_csv(csv_path, only_impl=False):
    """Open CSV_PATH and return the output of get_condensed based on csv."""
    with open(csv_path, 'rb') as filep:
        return get_condensed(filep, only_impl)


def load_csv(csv_root, fpath=None, only_impl=False):
    """Return a dict representing an analysis of a source file.

    :arg csv_root: A path to the folder containing the CSVs emitted by the
        compiler plugin
    :arg fpath: A path to the file to analyze, relative to the tree's source
        folder

    """
    hashed_fname = '*' if fpath is None else sha1(fpath).hexdigest()
    csv_paths = glob('{0}.*.csv'.format(path.join(csv_root, hashed_fname)))

    return reduce(merge, imap(_load_csv(only_impl=only_impl), csv_paths),
                  dict((key, []) for key in POSSIBLE_FIELDS))


# TODO: Perhaps remove.
def call_graph(condensed, inherit=None):
    """Return DiGraph with edges representing function caller -> callee."""
    graph = {}
    if inherit is None:
        inherit = build_inheritance(condensed)

    for call in condensed['call']:
        graph[call] = call
        if call.calltype == 'virtual':
            # add children
            callee_qname, pos = call.callee
            if '::' in callee_qname:
                scope, func = callee_qname.split('::')
                for child in inherit[scope]:
                    child_qname = "{0}::{1}".format(child, func)
                    graph[(call.caller, (child_qname, pos), 'virtual')] = call
    return graph


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
