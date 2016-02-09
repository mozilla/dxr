from itertools import chain

from dxr.indexers import (iterable_per_line, with_start_and_end,
                          split_into_lines)


# TODO: Use.
def sig_needles(condensed):
    """Return needles ((c-sig, type), span)."""
    return ((('c-sig', str(o['type'])), o['span']) for o in
            condensed['function'])


def needles(condensed,
            name,
            suffix='',
            kind=None,
            subkind=None,
            include_qualname=True,
            include_typeless_qualname=False):
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
    :arg include_qualname: Whether we should include the qualified name in the
        returned needle value dict
    :arg include_typeless_qualname: Whether we should include the qualname but
        with arg types stripped off, e.g. turning functions from Foo::bar(int)
        to Foo::bar, so people don't need to know the types to search for
        them. ``include_qualname`` must also be true to enable this.

    """
    kind = kind or name
    matches_subkind = (lambda entity: entity.get('kind') == subkind if subkind
                       else lambda entity: True)

    def names(entity):
        """Return the name, qualname, and type-free qualname of an entity.

        This way, Moo::foo(int) can be found as "foo", "Moo::foo" or
        "Moo:foo(int)".

        """
        value = {'name': entity['name']}
        if include_qualname:
            qualname = value['qualname'] = entity['qualname']
            if include_typeless_qualname:
                try:
                    # This is good enough for functions but probably not for
                    # templates yet:
                    offset = qualname.index('(')
                except ValueError:
                    pass
                else:
                    value['qualname'] = [qualname, qualname[:offset]]
        return value

    return (('c_{0}{1}'.format(name, suffix),
             names(entity),
             entity['span'])
            for entity in condensed[kind] if matches_subkind(entity))


def ref_needles(condensed,
                name,
                subkind=None,
                include_qualname=True,
                include_typeless_qualname=False):
    """Return needles for references to a certain kind of language construct,
    e.g. functions, variables, or namespaces.

    References are assumed to have names and qualnames.

    :arg subkind: The value of the 'kind' key to insist on in things within
        ``condensed['ref']``. Defaults to ``name``.

    """
    subkind = subkind or name
    return needles(condensed,
                   name,
                   suffix='_ref',
                   kind='ref',
                   subkind=subkind,
                   include_qualname=include_qualname,
                   include_typeless_qualname=include_typeless_qualname)


def decl_needles(condensed, name, subkind=None, include_typeless_qualname=False):
    """Return needles for declarations of things.

    Things are assumed to have names and qualnames.

    """
    return needles(condensed,
                   name,
                   suffix='_decl',
                   kind='decldef',
                   subkind=subkind,
                   include_typeless_qualname=include_typeless_qualname)


def warning_needles(condensed):
    return (('c_warning', {'name': w['msg']}, w['span']) for w in
            condensed['warning'])


def warning_opt_needles(condensed):
    """Return needles about the command-line options that call forth warnings."""
    return (('c_warning_opt', {'name': w['opt']}, w['span']) for w in
            condensed['warning'] if 'opt' in w)


def macro_needles(condensed):
    return (('c_macro', {'name': m['name']}, m['span']) for m in
            condensed['macro'])


def _walk_graph(graph, root_qualname, seen):
    """Yield (qualname, name) pairs gleaned from recursively descending a
    graph, without any repeats.

    It is possible, while traversing the graph, to come up with duplicates: for
    instance, from diamond-shaped inheritance patterns. This isn't a problem
    for ES, since duplicates will be merged in the term index. But it makes the
    highlighter emit icky empty tag pairs.

    We also cut off cycles before we get back to the original ``root_qualname``.

    :arg seen: The set of qualnames traversed, so we can avoid cycles and
        dupes. Cycles shouldn't happen, but the clang compiler plugin is buggy,
        so sometimes they do.

    """
    direct_dests = graph.get(root_qualname, [])
    for dest_qualname, dest_name in direct_dests:
        if dest_qualname not in seen:  # Dodge duplicates and cycles.
            seen.add(dest_qualname)

            # Direct destinations:
            yield dest_qualname, dest_name

            # Indirect destinations. For instance, if something overrides my
            # subclass's override, it overrides me as well. Flatten this in
            # place to avoid deeply nested chain() calls that lead to stack
            # overflows, e.g. bug 1246700.
            for x in _walk_graph(graph, dest_qualname, seen):
                yield x


def needles_from_graph(graph, root_qualname, method_span, needle_name):
    """Yield the unique needles gleaned from recursively descending a graph.

    The returned needles start at the nodes the ``root_qualname`` points to,
    not at the root itself.

    :arg graph: A graph of this format::

        {'source qualname': [('dest qualname', 'dest name')]}

    :arg root_qualname: The graph key at which to begin
    :arg method_span: The span to emit for every needle (the same for each)
    :arg needle_name: The key to emit for every needle (the same for each)

    """
    pairs = _walk_graph(graph, root_qualname, set([root_qualname]))
    return ((needle_name,
             {'qualname': qualname, 'name': name},
             method_span) for qualname, name in pairs)


def overrides_needles(condensed, overrides):
    def base_methods_of(method_qualname, method_span):
        """Return an iterable of needles for methods overridden by
        ``method_qualname``, either directly or indirectly.

        """
        return needles_from_graph(overrides, method_qualname, method_span, 'c_overrides')

    for f in condensed['function']:
        for needle in base_methods_of(f['qualname'], f['span']):
            yield needle


def overridden_needles(condensed, overriddens):
    """Check each function to see if it's been overridden, using the data
    gathered from override sites during the whole-program pass. If it has,
    spit out "c_overridden" needles for its direct and indirect overrides.

    :arg overriddens: A map of qualnames of overridden methods pointing to
        lists of (qualname of overriding method, name of overriding method),
        gathered during the whole-program post-build pass::

        {'Base::foo()': [('Derived::foo()', 'foo')]}

    """
    def overrides_of(method_qualname, method_span):
        """Return an iterable of needles for methods that override
        ``method_qualname``, either directly or indirectly.

        """
        return needles_from_graph(overriddens, method_qualname, method_span, 'c_overridden')

    for f in condensed['function']:
        for needle in overrides_of(f['qualname'], f['span']):
            yield needle


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


def caller_needles(condensed, overriddens):
    """Plonk qualified needles down at callsites, pointing at called functions.

    If a call is virtual, add also any overrides of the method in derived
    classes, because the dispatch will be controlled by the runtime type of
    the object, and C++ will happily implicitly upcast derived instances to
    base ones.

    """
    for needle in needles(condensed, 'call'):
        yield needle
    for call in condensed['call']:
        if call['calltype'] == 'virtual':
            for needle_from_base_method in needles_from_graph(
                    overriddens, call['qualname'], call['span'], 'c_call'):
                yield needle_from_base_method


def inheritance_needles(condensed, parents, children):
    """Emit needles that let us find parent and child classes of classes."""
    for type in condensed['type']:
        if type['kind'] == 'class' or type['kind'] == 'struct':
            # Lay down needles at a class's line. These needles' values are
            # any classes that this class is a parent of.
            for needle in needles_from_graph(
                    children, type['qualname'], type['span'], 'c_bases'):
                yield needle
            # And these needles' values are the classes that this class is a
            # child of:
            for needle in needles_from_graph(
                    parents, type['qualname'], type['span'], 'c_derived'):
                yield needle


def all_needles(condensed, overrides, overriddens, parents, children):
    return iterable_per_line(with_start_and_end(split_into_lines(chain(
            needles(condensed, 'function', include_typeless_qualname=True),
            ref_needles(condensed, 'function', include_typeless_qualname=True),

            # Classes:
            needles(condensed, 'type'),
            ref_needles(condensed, 'type'),

            # Typedefs:
            needles(condensed, 'type', kind='typedef'),
            ref_needles(condensed, 'type', subkind='typedef'),

            needles(condensed, 'var', kind='variable'),
            ref_needles(condensed, 'var', subkind='variable'),

            needles(condensed, 'namespace'),
            ref_needles(condensed, 'namespace'),

            needles(condensed, 'namespace_alias'),
            ref_needles(condensed, 'namespace_alias'),

            macro_needles(condensed),
            ref_needles(condensed, 'macro', include_qualname=False),

            decl_needles(condensed, 'var', subkind='variable'),
            decl_needles(condensed, 'function', include_typeless_qualname=True),
            decl_needles(condensed, 'type'),

            warning_needles(condensed),
            warning_opt_needles(condensed),

            caller_needles(condensed, overriddens),

            overrides_needles(condensed, overrides),
            overridden_needles(condensed, overriddens),

            member_needles(condensed),

            inheritance_needles(condensed, parents, children),
    ))))
