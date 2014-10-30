from operator import itemgetter
from itertools import chain, izip
from functools import partial

from funcy import imap, is_mapping, repeat, icat

from dxr.indexers import (iterable_per_line, with_start_and_end,
                          split_into_lines, Extent, Position)


def sig_needles(condensed):
    """Return needles ((c-sig, type), span)."""
    return ((('c-sig', str(o['type'])), o['span']) for o in
            condensed['function'])


def inherit_needles(condensed, tag, func):
    """Return list of needles ((c-tag, val), span).

    :type func: str -> iterable
    :param func: Map node name to an iterable of other node names.
    :param tag: First element in the needle tuple

    """
    children = (izip(func(c['name']), repeat(c['span'])) for c
                in condensed['type'] if c['kind'] == 'class')

    return imap(lambda (a, (b, c)): ((a, b), c),
                izip(repeat('c-{0}'.format(tag)), icat(children)))


def child_needles(condensed, inherit):
    """Return needles representing subclass relationships.

    :type inherit: mapping parent:str -> Set child:str

    """
    return inherit_needles(condensed, 'child',
                           lambda name: inherit.get(name, []))


def parent_needles(condensed, inherit):
    """Return needles representing super class relationships.

    :type inherit: mapping parent:str -> Set child:str

    """
    def get_parents(name):
        return (parent for parent, children in inherit.items()
                if name in children)

    return inherit_needles(condensed, 'parent', get_parents)


# def needles(condensed, inherit, graph):
#     """Return all C plugin needles."""
#
#     return chain(
#         parent_needles(condensed, inherit),
#         child_needles(condensed, inherit),
#         sig_needles(condensed),
#     )


def needles(condensed, name, suffix='', kind=None, subkind=None, keys=('name', 'qualname')):
    """Return an iterable of needles computed from the condensed representation.

    Each needle is a (needle name, needle value dict, Extent) triple.

    :arg name: The main part of the needle name ("function" in
        "c_function") and the key under which the interesting things are
    :arg suffix: The ending of the needle name ("_ref" in "c_var_ref")
        stored in ``condensed``
    :arg kind: The key under which the interesting things are stored in
         ``condensed``. Defaults to the value of ``name``.
    :arg subkind: The value of the 'kind' key to insist on in things found
        within ``condensed[kind]``. None for no insistence.
    :arg keys: The keys that should be in the final needle value

    """
    kind = kind or name
    matches_subkind = (lambda entity: entity['kind'] == subkind if subkind
                       else lambda entity: True)
    return (('c_{0}{1}'.format(name, suffix),
             dict((k, entity[k]) for k in keys),
             entity['span'])
            for entity in condensed[kind] if matches_subkind(entity))


def qualified_needles(condensed, name, kind=None):
    """Return needles for a top-level kind of thing that has a name and qualname."""
    return needles(condensed, name, kind=kind)


def ref_needles(condensed, name, subkind=None, keys=('name', 'qualname')):
    """Return needles for references to a certain kind of thing.

    References are assumed to have names and qualnames.

    :arg subkind: The value of the 'kind' key to insist on in things within
        ``condensed['ref']``. Defaults to ``name``.

    """
    subkind = subkind or name
    return needles(condensed, name, suffix='_ref', kind='ref', subkind=subkind, keys=keys)


def decl_needles(condensed, name, subkind=None, keys=('name', 'qualname')):
    """Return needles for declarations of things.

    Things are assumed to have names and qualnames.

    """
    return needles(condensed, name, suffix='_decl', kind='decldef', subkind=subkind, keys=keys)


def warning_needles(condensed):
    return (('c_warning', {'name': w['msg']}, w['span']) for w in
            condensed['warning'])


def warning_opt_needles(condensed):
    """Return needles about the command-line options that call forth warnings."""
    return (('c_warning_opt', {'name': w['opt']}, w['span']) for w in
            condensed['warning'])


def macro_needles(condensed):
    return (('c_macro', {'name': m['name']}, m['span']) for m in
            condensed['macro'])


def overrides_needles(condensed):
    return (('c_overrides',
             {'name': f['overriddenname'], 'qualname': f['overriddenqualname']},
             f['span']) for f in condensed['function'] if 'overriddenname' in f)


def overridden_needles(overriddens):
    """Unpack "c_overridden" needles from the data gathered from override
    sites during the whole-program pass, and spit them out.

    :arg overriddens: An iterable of tuples encoding the overridden method
        names and where they were overridden

    """
    return list(('c_overridden',
             {'name': name, 'qualname': qualname},
             Extent(Position(None, row, col), Position(None, end_row, end_col)))
            for row, col, end_row, end_col, name, qualname in overriddens)


def member_needles(condensed):
    """Emit needles for anything that has a class scope."""
    return (('c_member',
             {'name': entity['scopename'], 'qualname': entity['scopequalname']},
             entity['span'])
            # Walk over all kinds of things: types, functions, vars. All of
            # them can belong to a scope.
            for kind in condensed.itervalues()
            for entity in kind
            if 'scopename' in entity)


def all_needles(condensed, inheritance, overriddens):
    return iterable_per_line(with_start_and_end(split_into_lines(chain(
            qualified_needles(condensed, 'function'),
            ref_needles(condensed, 'function'),

            # Classes:
            qualified_needles(condensed, 'type'),
            ref_needles(condensed, 'type'),

            # Typedefs:
            qualified_needles(condensed, 'type', kind='typedef'),
            ref_needles(condensed, 'type', subkind='typedef'),

            qualified_needles(condensed, 'var', kind='variable'),
            ref_needles(condensed, 'var', subkind='variable'),

            qualified_needles(condensed, 'namespace'),
            ref_needles(condensed, 'namespace'),

            qualified_needles(condensed, 'namespace_alias'),
            ref_needles(condensed, 'namespace_alias'),

            macro_needles(condensed),
            ref_needles(condensed, 'macro', keys=('name',)),

            decl_needles(condensed, 'var', subkind='variable'),
            decl_needles(condensed, 'function'),
            decl_needles(condensed, 'type'),

            warning_needles(condensed),
            warning_opt_needles(condensed),

            qualified_needles(condensed, 'call'),

            overrides_needles(condensed),
            overridden_needles(overriddens),

            member_needles(condensed),
    ))))
