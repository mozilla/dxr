"""Representation of a compiler-emitted CSV as a hash

Mirrors the intermediate representation of tern's condense output used by
the js plugin. [Actually, has diverged somewhat. There may not be a good
reason to keep this IR.]

"""
import csv
from functools import partial
from glob import glob
from hashlib import sha1
from itertools import chain, izip
from os.path import join

from funcy import decorator, identity, select_keys, imap, ifilter, remove

from dxr.indexers import FuncSig, Position, Extent
from dxr.utils import frozendict


class UselessLine(Exception):
    """A CSV line isn't suitable for getting anything useful out of."""


POSSIBLE_KINDS = ('call', 'macro', 'function', 'func_override', 'variable',
                  'ref', 'type', 'impl', 'decldef', 'typedef', 'warning',
                  'namespace', 'namespace_alias', 'include')


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


def process_maybe_override(overrides, overriddens, props):
    """Add 'has_overriddens', 'has_overrides' properties to props if the
    qualname of this function appears in overrides, respectively
    overriddens.

    """
    qualname = props.get('qualname')
    if qualname in overrides:
        # Keys of overrides are functions that override something, so this
        # function has overriddens in the sense of the "Find overriddens" menu
        # option.
        props['has_overriddens'] = True
    if qualname in overriddens:
        props['has_overrides'] = True

    return props


def process_maybe_function(overrides, overriddens, props):
    """If these are props for a function, add 'has_overrides', 'has_overriddens'
    properties to props if overrides, respectively overriddens exist.

    """
    if props.get('kind') == 'function':
        return process_maybe_override(overrides, overriddens, props)
    else:
        return props


def process_function_for_override(overrides, overriddens, props):
    """Add 'has_overrides', 'has_overriddens' keys to props if overrides,
    respectively overriddens exist, and add a 'type' key to props whose value
    is the call signature of this function.

    """
    override_props = process_maybe_override(overrides, overriddens, props)
    return process_function(override_props)


def process_override(overrides, overriddens, props):
    """Note overrides of methods, and organize them so we can emit
    "overridden" and "overrides" needles later.

    Specifically, extract the qualname of the overridden method and the
    qualname and name of the overriding method, and squirrel it away in
    ``overriddens``, keyed by base qualname::

        {'Base::foo()': set([('Derived::foo()', 'foo')])}

    Also store the reverse mapping (override to overridden), in ``overrides``::

        {'Derived::foo()': set([('Base::foo()', 'foo')])}

    This lets return indirect overrides (not just direct ones) in "overrides"
    queries.

    """
    # It may not be necessary to have a list here. In multiple inheritance,
    # does clang ever consider a method to override multiple other methods, or
    # is it at most one each?  Answer: clang recognizes multiple overriddens.
    overrides.setdefault(props['qualname'], set()).add(
            (props['overriddenqualname'], props['overriddenname']))

    # We store the unqualified name separately for each override because,
    # while it's usually the same for each, it can be different for an
    # overridden destructor.
    overriddens.setdefault(props['overriddenqualname'], set()).add(
            (props['qualname'], props['name']))

    # No sense wasting RAM remembering anything:
    raise UselessLine


@without('loc', 'locend')
def process_span(props):
    """Turn the "loc" and "locend" fields into a "span" that's an Extent."""
    if not props.get('locend', ''):  # locend can be "" if isInvalid().
        # This happens with some macros which call other macros, like this:
        #   #define ID2(x) (x)
        #   #define ID(x) ID2(x)
        # In the second line, ID2 will get a macro ref line, but it will lack
        # an extent because the SourceLocation of ID2 will not be .isValid().
        # We never got that right, even in the SQLite implementation.
        raise UselessLine('Found a line with "loc" but without "locend".')

    _, row, col = _split_loc(props['loc'])
    _, row_end, col_end = _split_loc(props['locend'])
    props['span'] = Extent(Position(row, col),
                           Position(row_end, col_end))

    return props


def _split_loc(locstring):
    """Turn a path:row:col string into (path, row, col)."""
    if not locstring:
        # Empty loc or locend means the SourceLocation was invalid.
        raise UselessLine
    path, row, col = locstring.rsplit(':', 2)
    return path, int(row), int(col)


def _process_loc(locstring):
    """Turn a path:row:col string into (path, Position)."""
    src, row, col = _split_loc(locstring)
    return src, Position(row, col)


def process_maybe_impl(parents, children, props):
    """Add 'has_base_class', 'has_subclass' properties to props if these props
    are for a class or a struct that has parents, respectively children.

    """
    if props.get('kind') == 'class' or props.get('kind') == 'struct':
        if props.get('qualname') in parents:
            props['has_base_class'] = True
        if props.get('qualname') in children:
            props['has_subclass'] = True

    return props


def process_impl(parents, children, props):
    """Contribute to the whole-program class hierarchy graphs.

    :arg children: A dict that points from parents to children::

        {'Some::Parent': set([('A::Child', 'Child')])}

    :arg parents: A dict that points from children to parents::

        {'A::Child': set([('Some::Parent', 'Parent)])}

    """
    parents.setdefault(props['qualname'], set()).add(
        (props['basequalname'], props['basename']))
    children.setdefault(props['basequalname'], set()).add(
        (props['qualname'], props['name']))

    # No need to waste memory keeping this in the per-file store:
    raise UselessLine


@without('callloc', 'calllocend')
def process_call(props):
    _, call_start = _process_loc(props['callloc'])
    _, (call_end_row, call_end_col) = _process_loc(props['calllocend'])
    # The span coming out of the compiler excludes the right paren.
    call_end_col += 1
    props['span'] = Extent(call_start,
                           Position(row=call_end_row, col=call_end_col))
    props['calleeloc'] = _process_loc(props['calleeloc'])  # for Jump To
    return props


def condense_line(dispatch_table, kind, fields):
    """Digest one CSV row into an intermediate form.

    :arg dispatch_table: A map of kinds to functions that transform ``fields``
    :arg kind: The first field of the row, identifying the type of thing it
        represents: "function", "impl", etc.
    :arg fields: The map constructed from the row's alternating keys and values

    """
    fields = dispatch_table.get(kind, identity)(fields)

    if 'loc' in fields:
        fields = process_span(fields)

    if 'declloc' in fields:
        fields['declloc'] = _process_loc(fields['declloc'])

    if 'defloc' in fields:
        fields['defloc'] = _process_loc(fields['defloc'])

    return frozendict(fields)


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
    ret = dict((key, set()) for key in POSSIBLE_KINDS)
    for line in lines:
        kind = line[0]
        fields = dict(izip(line[1::2], line[2::2]))
        if not predicate(kind, fields):
            continue

        try:
            ret[kind].add(condense_line(dispatch_table, kind, fields))
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

    # This globbing is stupid but actually not that slow: a few tenths of a
    # second on a dir of 97K files in VirtualBox. That said, it does add up.
    paths = glob(join(folder, file_glob))
    return chain.from_iterable(lines_from_csv(p) for p in paths)


def condense_file(csv_folder, file_path, overrides, overriddens, parents, children):
    """Return a dict representing an analysis of one source file.

    This is phase 2: the file-at-a-time phase.

    This may comprise several CSVs if, for example, preprocessor magic results
    in the file being built several different times, with different effective
    contents each time.

    :arg csv_folder: A path to the folder containing the CSVs emitted by the
        compiler plugin
    :arg file_path: A path to the file to analyze, relative to the tree's
        source folder
    :arg overrides: A dict whose keys are function qualnames that are overrides
    :arg overriddens: A dict whose keys are function qualnames that are
        overriddens
    :arg parents: A dict whose keys are class or struct qualnames that have
        parents
    :arg children: A dict whose keys are class or struct qualnames that have
        children

    """
    process_maybe_function_for_override = partial(process_maybe_function,
                                                  overrides, overriddens)

    dispatch_table = {'call': process_call,
                      'function': partial(process_function_for_override,
                                          overrides, overriddens),
                      'ref': process_maybe_function_for_override,
                      'decldef': process_maybe_function_for_override,
                      'type': partial(process_maybe_impl, parents, children)}

    return condense(lines_from_csvs(csv_folder,
                                    '{0}.*.csv'.format(sha1(file_path).hexdigest())),
                    dispatch_table)


def condense_global(csv_folder):
    """Perform the whole-program data gathering necessary to emit "overridden"
    and subclass-related needles.

    This is phase 1: the whole-program phase.

    """
    def listify_keys(d):
        """For a dict having values that are sets, turn those into lists."""
        for k, v in d.iteritems():
            d[k] = list(v)

    # process_override() squirrels things away in these:
    overrides = {}
    overriddens = {}
    # ...and process_impl() in these:
    parents = {}
    children = {}

    # Load from all the CSVs only the impl lines and {function lines
    # containing overriddenname}. Ignore the direct return value and collect
    # what we want via the partials.
    condense(
        lines_from_csvs(csv_folder, '*.csv'),
        {'impl': partial(process_impl, parents, children),
         'func_override': partial(process_override, overrides, overriddens)},
        predicate=lambda kind, fields: (kind == 'func_override' or
                                        kind == 'impl'))

    # Turn some sets into lists. There's no need to keep them as sets, and
    # lists are tighter on RAM, which will make them faster to pass to workers.
    for x in [overrides, overriddens, parents, children]:
        listify_keys(x)

    return overrides, overriddens, parents, children
