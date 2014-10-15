import os
import sys
from operator import itemgetter
from itertools import chain, izip, ifilter
from functools import partial

from funcy import (merge, imap, group_by, is_mapping, repeat,
                   constantly, icat, autocurry)

from dxr.filters import LINE
from dxr.indexers import FileToIndex as FileToIndexBase, TreeToIndex as TreeToIndexBase
from dxr.indexers import unsparsify_func, group_needles, by_line
from dxr.plugins.clang.condense import load_csv, build_inheritance, call_graph
from dxr.plugins.clang.menus import (function_menu, variable_menu, type_menu,
                                     namespace_menu, namespace_alias_menu,
                                     macro_menu, include_menu, typedef_menu,
                                     definition_menu)


PLUGIN_NAME = 'clang'


# An unanlyzed string property that points to a value that can be exact- or
# prefix-matched against and carries start/end bounds for highlighting:
UNANALYZED_EXTENT_NEEDLE = {
    'type': 'object',
    'properties': {
        'value': {
            'type': 'string',
            'index': 'not_analyzed',  # TODO: case-insensitive
        },
        'start': {
            'type': 'integer',
            'index': 'no'  # just for highlighting
        },
        'end': {
            'type': 'integer',
            'index': 'no'
        }
    }
}


mappings = {
    LINE: {
        'properties': {
            'c-function': UNANALYZED_EXTENT_NEEDLE,
            'c-function-ref': UNANALYZED_EXTENT_NEEDLE,
            'c-function-decl': UNANALYZED_EXTENT_NEEDLE,
            'c-type-ref': UNANALYZED_EXTENT_NEEDLE,
            'c-type-decl': UNANALYZED_EXTENT_NEEDLE,
            'c-type': UNANALYZED_EXTENT_NEEDLE,
            'c-var': UNANALYZED_EXTENT_NEEDLE,
            'c-var-ref': UNANALYZED_EXTENT_NEEDLE,
            'c-var-decl': UNANALYZED_EXTENT_NEEDLE,
            'c-macro': UNANALYZED_EXTENT_NEEDLE,
            'c-macro-ref': UNANALYZED_EXTENT_NEEDLE,
            'c-namespace': UNANALYZED_EXTENT_NEEDLE,
            'c-namespace-ref': UNANALYZED_EXTENT_NEEDLE,
            'c-namespace-alias': UNANALYZED_EXTENT_NEEDLE,
            'c-namespace-alias-ref': UNANALYZED_EXTENT_NEEDLE,
            'c-warning': UNANALYZED_EXTENT_NEEDLE,
            'c-warning-opt': UNANALYZED_EXTENT_NEEDLE,
            'c-called-by': UNANALYZED_EXTENT_NEEDLE,
            'c-callers': UNANALYZED_EXTENT_NEEDLE,
            'c-bases': UNANALYZED_EXTENT_NEEDLE,
            'c-derived': UNANALYZED_EXTENT_NEEDLE,
            'c-member': UNANALYZED_EXTENT_NEEDLE,
            'c-overrides': UNANALYZED_EXTENT_NEEDLE,
            'c-overridden': UNANALYZED_EXTENT_NEEDLE
        }
    }
}


def _members(condensed, key, id_):
    """Fetch member {{key}} given a type id."""
    pred = lambda x: id_ == x['qualname']
    for props in ifilter(pred, condensed[key]):
        # Skip nameless things
        name = props['qualname']
        (_, line, _), _ = props['span']
        if not name:
            continue
        yield 'method', name, "#%s" % line


class FileToIndex(FileToIndexBase):
    """C and C++ indexer using clang compiler plugin"""

    def __init__(self, path, contents, tree, inherit):
        super(FileToIndex, self).__init__(path, contents, tree)
        self.inherit = inherit
        self.condensed = load_csv(*os.path.split(path))
        graph = call_graph(self.condensed, inherit)
        self._needles, self._needles_by_line = needles(self.condensed, inherit,
                                                       graph)

    def needles(self):
        return self._needles  # Are there ever any of these?

    @unsparsify_func
    def needles_by_line(self):
        return self._needles_by_line

    def refs(self):
        def silent_itemgetter(y):
            return lambda x: x.get(y, [])

        # Refs are not structured much like functions, but they have a
        # qualname key, which is all that function_menu() requires, so we can
        # just chain kind_getters together with other getters.
        #
        # Menu makers and the thing-getters over which they run:
        menus_and_views = [
                (function_menu, [silent_itemgetter('function'),
                                 kind_getter('ref', 'function')]),
                (variable_menu, [silent_itemgetter('variable'),
                                 kind_getter('ref', 'variable')]),
                (type_menu, [silent_itemgetter('type'),
                             kind_getter('ref', 'type')]),
                (type_menu, [silent_itemgetter('decldef')]),
                (typedef_menu, [silent_itemgetter('typedef'),
                                kind_getter('ref', 'typedef')]),
                (namespace_menu, [silent_itemgetter('namespace'),
                                  kind_getter('ref', 'namespace')]),
                (namespace_alias_menu, [silent_itemgetter('namespace_alias'),
                                        kind_getter('ref', 'namespace_alias')]),
                (macro_menu,
                 [silent_itemgetter('macro'), kind_getter('ref', 'macro')],
                 silent_itemgetter('text')),
                (include_menu, [silent_itemgetter('include')])]
        return chain.from_iterable(self._refs_from_view(*mv) for mv in
                                   menus_and_views)

    @unsparsify_func
    def annotations_by_line(self):
        icon = "background-image: url('{0}/static/icons/warning.png');".format(
            self.tree.config.wwwroot)  # TODO: DRY
        getter = itemgetter('msg', 'opt', 'span')
        for msg, opt, span in imap(getter, self.condensed.get('warnings', [])):
            if opt:
                msg = "{0}[{1}]".format(msg, opt)
            annotation = {
                'title': msg,
                'class': "note note-warning",
                'style': icon
            }
            yield annotation, span

    def _refs_from_view(self, menu_maker, views, tooltip=constantly(None)):
        """Return an iterable of (start, end, (menu, tooltip)), running
        ``menu_maker`` across each item that comes of applying ``view`` to
        ``self.condensed`` and adding "Jump to definition" where applicable.

        :arg menu_maker: A function that takes a tree and an item from
            ``view()`` and returns a ref menu
        :arg views: An iterable of functions that take self.condensed and
            return an iterable of things to call ``menu_maker()`` on
        :arg tooltip: A function that takes one of those things from the
            iterable and emits a value to be shown in the mouseover of the ref

        """
        for prop in chain.from_iterable(v(self.condensed) for v in views):
            if 'span' in prop:  # TODO: This used to be unconditional. Should we still try to do it sometime if span isn't in prop? Both cases in test_direct are examples of this. [Marcell says no.]
                if 'declloc' in prop:  # if we can look up the target of this ref
                    menu = definition_menu(self.tree,
                                           path=prop['declloc'][0],
                                           row=prop['declloc'][1].row)
                else:
                    menu = []

                menu.extend(menu_maker(self.tree, prop))
                start, end = prop['span']

                if start.offset is None or end.offset is None:
                    raise NotImplementedError("Fix this logic. It's full of holes. We must return a file-wide offset, but Position.offset was None.")
                yield start.offset, end.offset, (menu, tooltip(prop))

    def links(self):
        # For each type add a section with members

        getter = itemgetter('name', 'qualname', 'span', 'kind')
        for name, tid, span, kind in imap(getter, self.condensed['type']):
            (_, line, _), _ = span
            if len(name) == 0:
                continue

            # Make sure we have a sane limitation of kind
            if kind not in ('class', 'struct', 'enum', 'union'):
                print >> sys.stderr, "kind '%s' was replaced for 'type'!" % kind
                kind = 'type'

            links = chain(_members(self.condensed, 'function', tid),
                          _members(self.condensed, 'variable', tid))

            links = sorted(links, key=itemgetter(1))  # by line

            # Add the outer type as the first link
            links = [(kind, name, "#%s" % line)] + links

            yield 30, name, links

        # Add all macros to the macro section
        links = []
        getter = itemgetter('name', 'span')
        for name, span in imap(getter, self.condensed['type']):
            (_, line, _), _ = span
            links.append(('macro', name, "#%s" % line))
        if links:
            yield 100, "Macros", links


@autocurry
def kind_getter(field, kind, condensed):
    """Reach into a field and filter based on the kind."""
    return (ref for ref in condensed.get(field) if ref['kind'] == kind)


def pluck2(key1, key2, mappings):
    """Plucks a pair of keys from mappings.

    This is a generalization of funcy's pluck function.
    (k1, k2, {k: v}) -> [(v1, v2)]

    """
    return imap(itemgetter(key1, key2), mappings)


def group_sparse_needles(needles_):
    """Return a pair of iterators (file_needles, line_needles)."""
    needles_ = group_by(lambda x: 'file' if x[1] is None else 'line', needles_)
    return needles_['file'], needles_['line']


def _name_needles(condensed, key, name_key):
    """Helper function for name_needles.

    :param name_key: key to access the name of a property

    """
    names = (('c-{0}'.format(key.replace('_', '-')), props[name_key])
             for props in condensed[key] if name_key in props)
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


def needles(condensed, inherit, graph):
    """Return all C plugin needles."""

    return group_sparse_needles(chain(
        name_needles(condensed, 'function'),
        name_needles(condensed, 'variable'),
        name_needles(condensed, 'typedef'),
        name_needles(condensed, 'macro'),
        name_needles(condensed, 'namespace'),
        name_needles(condensed, 'namespace_alias'),
        warn_needles(condensed),
        warn_op_needles(condensed),
        callee_needles(graph),
        caller_needles(graph),
        parent_needles(condensed, inherit),
        child_needles(condensed, inherit),
        member_needles(condensed),
        overridden_needles(condensed),
        overrides_needles(condensed),
        type_needles(condensed),
        sig_needles(condensed)
    ))


class TreeToIndex(TreeToIndexBase):
    def environment(self, vars_):
        """Setup environment variables for inspecting clang as runtime

        We'll store all the havested metadata in the plugins temporary folder.

        """
        tree = self.tree
        temp_folder = os.path.join(tree.temp_folder, 'plugins', PLUGIN_NAME)
        self._temp_folder = temp_folder
        plugin_folder = os.path.join(tree.config.plugin_folder, PLUGIN_NAME)
        flags = [
            '-load', os.path.join(plugin_folder, 'libclang-index-plugin.so'),
            '-add-plugin', 'dxr-index',
            '-plugin-arg-dxr-index', tree.source_folder
        ]
        flags_str = " ".join(imap('-Xclang {}'.format, flags))

        env = {
            'CC': "clang %s" % flags_str,
            'CXX': "clang++ %s" % flags_str,
            'DXR_CLANG_FLAGS': flags_str,
            'DXR_CXX_CLANG_OBJECT_FOLDER': tree.object_folder,
            'DXR_CXX_CLANG_TEMP_FOLDER': temp_folder,
        }
        env['DXR_CC'] = env['CC']
        env['DXR_CXX'] = env['CXX']
        return merge(vars_, env)

    def post_build(self):
        condensed = load_csv(self._temp_folder, fpath=None, only_impl=True)
        self._inherit = build_inheritance(condensed)

    def file_to_index(self, path, contents):
        return FileToIndex(os.path.join(
                self._temp_folder, path), contents, self.tree, self._inherit)
