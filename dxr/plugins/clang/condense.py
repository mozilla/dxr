"""Mirrors the intermediate representation of tern's condense output used by
the js plugin.

"""

import csv
from hashlib import sha1
from os import path
from glob import glob

from funcy import first, walk, walk_keys, decorator, identity, select_keys
from funcy import zipdict, merge, partial

from dxr.plugins.utils import FuncSig, Position, Extent


@decorator
def without(call, *keys):
    """Returns dictionary without the given keys"""
    return select_keys(lambda k: k not in keys, call())


@without('!args')
def process_function(props):
    """Create !type: FuncSig based on !args."""
    input_args = map(str.lstrip, props['!args'][1:-1].split(","))
    props['!type'] = FuncSig(input_args, props['!type'])
    return props


@without('!loc', '!extent')
def process_loc(props):
    """Create extent based on !loc and !extent."""
    _, row, col = props['!loc'].split(':')
    start, end = props['!extent'].split(':')
    props['!span'] = Extent(Position(start, row, col), Position(end, row, col))
    return props


def process_declloc(props):
    """Create Position based on declloc."""
    src, row, col = props['!declloc'].split(':')
    props['!declloc'] = src, Position(None, row, col)
    return props


def process_call(props):
    """Group caller and callee for the call site."""
    return group_loc_name('caller', group_loc_name('callee', props))


def process_scope(props):
    """Group scopeloc and scopename into a scope field."""
    return group_loc_name('scope', props)


def group_loc_name(base, props):
    """Group the loc and name fields into a base field."""
    root = '!{0}'.format(base)
    name, loc = '!{0}name'.format(base), '!{0}loc'.format(base)

    @without(name, loc)
    def _group_loc_name(props):
        src, row, col = props[loc].split(':')
        props[root] = {'!loc': (src, Position(None, row, col)),
                       '!name': props[name]}
        return props
    return _group_loc_name(props)


def process_fields(fields):
    """Return new fields dict based on the current contents."""
    if isinstance(fields, dict):
        fields = walk_keys('!{0}'.format, fields)

    if '!name' in fields:
        fields = without('!name')(identity)(fields)

    if '!loc' in fields:
        fields = process_loc(fields)

    if '!args' in fields:
        fields = process_function(fields)

    if '!scopeloc' in fields:
        fields = process_scope(fields)

    if '!declloc' in fields:
        fields = process_declloc(fields)

    return fields


def process((kind, fields)):
    """Process row from csv output."""
    fields = process_fields(fields)
    if kind in ('!refs', '!calls', '!warnings'):
        fields = map(process_fields, fields)

    if kind == '!calls':
        fields = map(process_call, fields)
    return (kind, fields)


def _get_condensed(fpath, csv_path):
    with open(csv_path, 'rb') as f:
        rows = [(line[0], zipdict(line[1::2], line[2::2])) for line
                in csv.reader(f)]

    def get_kinds(kind):
        return [props for _kind, props in rows if kind == _kind]

    condensed = dict((props['name'], props) for _, props in rows if "name"
                     in props)
    condensed['!name'] = fpath
    condensed['!refs'] = get_kinds('ref')
    condensed['!calls'] = get_kinds('call')
    condensed['!warnings'] = get_kinds('warning')
    return condensed
    

def load_csv(csv_root, fpath):
    """Given a path to a build csv, return a dict representing the analysis."""
    csv_paths = glob("{0}.*.csv".format(
        path.join(csv_root, sha1(fpath).hexdigest())))
    
    return reduce(merge, map(partial(_get_condensed, fpath), csv_paths), {})
