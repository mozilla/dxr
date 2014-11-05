"""Representation of a compiler-emitted CSV as a hash

Mirrors the intermediate representation of tern's condense output used by
the js plugin. [Actually, has diverged somewhat. There may not be a good
reason to keep this IR.]

"""
import csv
from functools import partial
from hashlib import sha1
from itertools import chain, izip
from os.path import join
from glob import glob

from funcy import (walk, decorator, identity, select_keys, imap,
                   ifilter, group_by, remove)
from toposort import toposort_flatten

from dxr.indexers import FuncSig, Position, Extent


class UselessLine(Exception):
    """A CSV line isn't suitable for getting anything useful out of."""


POSSIBLE_KINDS = set(['call', 'macro', 'function', 'variable', 'ref',
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
    return props


def process_override(overrides, overriddens, props):
    """Note overrides of methods, and organize them so we can emit
    "overridden" and "overrides" needles later.

    Specifically, extract the qualname of the overridden method and the
    qualname and name of the overriding method, and squirrel it away in
    ``overriddens``, keyed by base qualname::

        {'Base::foo()': [('Derived::foo()', 'foo')]}

    Also store the reverse mapping (override to overridden), in ``overrides``::

        {'Derived::foo()': [('Base::foo()', 'foo')]}

    This lets return indirect overrides (not just direct ones) in "overrides"
    queries.

    """
    # The loc points to the overridden (superclass) method.
    path, row, col = _split_loc(props['overriddenloc'])

    # It may not be necessary to have a list here. In multiple inheritance,
    # does clang ever consider a method to override multiple other methods, or
    # is it at most one each?
    overrides.setdefault(props['qualname'], []).append(
            (props['overriddenqualname'], props['overriddenname']))

    # We store the unqualified name separately for each override because,
    # while it's usually the same for each, it can be different for an
    # overridden destructor.
    overriddens.setdefault(props['overriddenqualname'], []).append(
            (props['qualname'], props['name']))

    # No sense wasting RAM remembering anything:
    raise UselessLine


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


def _split_loc(locstring):
    """Turn a path:row:col string into (path, row, col)."""
    path, row, col = locstring.rsplit(':', 2)
    return path, int(row), int(col)


def _process_loc(locstring):
    """Turn a path:row:col string into (path, Position)."""
    if locstring is None:
        return None

    src, row, col = _split_loc(locstring)
    return src, Position(None, row, col)


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


def _relate((parent, children)):
    return parent, set((child['tc']['name']) for child in children)


def build_inheritance(subclasses):
    """Builds mapping class -> set of all descendants."""
    get_tbname = lambda x: x['tb']['name']  # tb are parents, tc are children
    tree = walk(_relate, group_by(get_tbname, subclasses))
    tree.default_factory = set
    for node in toposort_flatten(tree):
        children = tree[node]
        for child in set(children):
            tree[node] |= tree[child]
    return tree


def condense_line(dispatch_table, kind, fields):
    """Digest one CSV row into an intermediate form.

    :arg dispatch_table: A map of kinds to functions that transform ``fields``
    :arg kind: The first field of the row, identifying the type of thing it
        represents: "function", "impl", etc.
    :arg fields: The map constructed from the row's alternating keys and values

    """
    fields = dispatch_table.get(kind, identity)(fields)

    if 'loc' in fields:
        fields = process_loc(fields)

    if 'declloc' in fields:
        fields = process_declloc(fields)

    if 'defloc' in fields:
        fields = process_defloc(fields)

    return fields


def condense(lines, dispatch_table, predicate=lambda kind, fields: True):
    """Return a dict representing an analysis of one or more source files.

    This function just takes a bunch of CSV lines; it doesn't concern itself
    with where they come from.

    :arg lines: An iterable of lists of strings. The first item of each list
        is the "kind" of the line: function, call, impl, etc. The rest are
        arbitrary alternating keys and values.
    :arg dispatch_table: A map of kinds to functions that transform the
        key/value dict extracted from each line.
    :arg predicate: A function that returns whether we should pay any
        attention to a line. If it returns False, the line is thrown away.

    """
    ret = dict((key, []) for key in POSSIBLE_KINDS)
    for line in lines:
        kind = line[0]
        fields = dict(izip(line[1::2], line[2::2]))
        if not predicate(kind, fields):
            continue

        try:
            ret[kind].append(condense_line(dispatch_table, kind, fields))
        except UselessLine:
            pass
    return ret


def lines_from_csvs(folder, file_glob):
    """Return an iterable of lines from all CSVs matching a glob.

    All lines are lists of strings.

    :arg folder: The folder in which to look for CSVs
    :arg file_glob: A glob matching one or more CSVs in the folder

    """
    def lines_from_csv(path):
        with open(path, 'rb') as file:
            # Loop internally so we don't prematurely close the file:
            for line in csv.reader(file):
                yield line

    paths = glob(join(folder, file_glob))
    return chain.from_iterable(lines_from_csv(p) for p in paths)


DISPATCH_TABLE = {'call': process_call,
                  'function': process_function,
                  'impl': process_impl}
def condense_file(csv_folder, file_path):
    """Return a dict representing an analysis of one source file.

    This is phase 2: the file-at-a-time phase.

    This may comprise several CSVs if, for example, proprocessor magic results
    in the file being built several different times, with different effective
    contents each time.

    :arg csv_folder: A path to the folder containing the CSVs emitted by the
        compiler plugin
    :arg file_path: A path to the file to analyze, relative to the tree's
        source folder

    """
    return condense(lines_from_csvs(csv_folder,
                                    '{0}.*.csv'.format(sha1(file_path).hexdigest())),
                    DISPATCH_TABLE)


def inheritance_and_overrides(csv_folder):
    """Perform the whole-program data gathering necessary to emit "overridden"
    and subclass-related needles.

    This is phase 1: the whole-program phase.

    """
    # process_override() squirrels things away in these:
    overrides = {}
    overriddens = {}

    # Load from all the CSVs only the impl lines and {function lines
    # containing overriddenname}:
    condensed = condense(
        lines_from_csvs(csv_folder, '*.csv'),
        {'impl': process_impl,
         'function': partial(process_override, overrides, overriddens)},
        predicate=lambda kind, fields: (kind == 'function' and
                                        'overriddenname' in fields) or
                                       kind == 'impl')
    return build_inheritance(condensed['impl']), overrides, overriddens
