from operator import itemgetter
from itertools import chain, izip
from functools import partial

from funcy import imap, group_by, is_mapping, repeat, icat

from dxr.indexers import group_by_line, with_start_and_end, split_into_lines


def _name_needles(condensed, key, name_key):
    """Helper function for name_needles.

    :param name_key: key to access the name of a property

    """
    names = (('c-{0}'.format(key.replace('_', '-')), props[name_key])
             for props in condensed[key] if name_key in props)
    # How are names and spans(...) going to align? spans() doesn't do the "if name_key in props" bit.
    return izip(names, spans(condensed, key))


def name_needles(condensed, key, ):
    """Return needles ((c-key, name), span).

    :param key: name of entry in condensed to get names from

    """
    return chain(_name_needles(condensed, key, 'name'),
                 _name_needles(condensed, key, 'qualname'))


def spans(condensed, key):
    """Return list of spans from condensed.

    :arg key: name of entry in condensed to get spans from

    """
    return imap(itemgetter('span'), condensed[key])


def warn_needles(condensed):
    """Return needles (('c-warning', msg), span)."""
    return izip((('c-warning', props['msg']) for props
                 in condensed['warning']), spans(condensed, 'warning'))


def warn_op_needles(condensed):
    """Return needles (('c-warning-opt', opt), span)."""
    return izip((('c-warning-opt', props['opt']) for props
                 in condensed['warning']), spans(condensed, 'warning'))


def callee_needles(graph):
    """Return needles (('c-callee', callee name), span)."""
    return ((('c-callee', call.callee[0]), call.callee[1]) for call
            in graph)


def caller_needles(graph):
    """Return needles (('c-needle', caller name), span)."""
    return ((('c-called-by', call.caller[0]), call.caller[1]) for call
            in graph)


def type_needles(condensed):
    """Return needles ((c-type, type), span)."""
    return ((('c-type', o['name']), o['span']) for o in condensed['type'])


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


def member_needles(condensed):
    """Return needles for the scopes that various symbols belong to."""
    for vals in condensed.itervalues():
        # Many of the fields are grouped by kind
        if is_mapping(vals):
            continue
        for val in vals:
            if 'scope' not in val:
                continue
            yield ('c-member', val['scope']['name']), val['span']


def _over_needles(condensed, tag, name_key, get_span):
    return ((('c-{0}'.format(tag), func['override'][name_key]), get_span(func))
            for func in condensed['function']
            if name_key in func.get('override', []))


def overrides_needles(condensed):
    """Return needles of methods which override the given one."""
    _overrides_needles = partial(_over_needles, condensed=condensed,
                                tag='overrides', get_span=itemgetter('span'))
    return chain(_overrides_needles(name_key='name'),
                 _overrides_needles(name_key='qualname'))


def overridden_needles(condensed):
    """Return needles of methods which are overridden by the given one."""
    get_span = lambda x: x['override']['span']
    _overriden_needles = partial(_over_needles, condensed=condensed,
                                 tag='overridden', get_span=get_span)
    return chain(_overriden_needles(name_key='name'),
                 _overriden_needles(name_key='qualname'))


# def needles(condensed, inherit, graph):
#     """Return all C plugin needles."""
#
#     return chain(
#         name_needles(condensed, 'function'),
#         name_needles(condensed, 'variable'),
#         name_needles(condensed, 'typedef'),
#         name_needles(condensed, 'macro'),
#         name_needles(condensed, 'namespace'),
#         name_needles(condensed, 'namespace_alias'),
#         warn_needles(condensed),
#         warn_op_needles(condensed),
#         callee_needles(graph),
#         caller_needles(graph),
#         parent_needles(condensed, inherit),
#         child_needles(condensed, inherit),
#         member_needles(condensed),
#         overridden_needles(condensed),
#         overrides_needles(condensed),
#         type_needles(condensed),
#         sig_needles(condensed),
#         # TODO: Add ref needles. Should be easy.
#     )

def symbol_needles(condensed, kind):
    """Return needles for a kind of thing that has a name and qualname.

    :arg kind: The main part of the needle name ("function" in "c-function")
        and the key under which the interesting things are stored in
        ``condensed``

    """
    return (('c-{0}'.format(kind),
             {'name': f['name'], 'qualname': f['qualname']},
             f['span'])
            for f in condensed[kind])


def ref_needles(condensed, kind):
    """Return needles for references to a certain kind of thing.

    References are assumed to have names and qualnames.

    :arg kind: The main part of the needle name ("function" in
        "c-function-ref") and the key under which the interesting things are
        stored in ``condensed['refs']``

    """
    return [('c-{0}-ref'.format(kind),
             {'name': f['name'], 'qualname': f['qualname']},
             f['span'])
            for f in condensed['ref'] if f['kind'] == kind]


def warning_needles(condensed):
    return (('c-warning', {'name': w['msg']}, w['span']) for w in condensed['warning'])


def needles(condensed, _1, _2):
    return group_by_line(with_start_and_end(split_into_lines(chain(
            symbol_needles(condensed, 'function'),
            ref_needles(condensed, 'function'),
            warning_needles(condensed)))))
