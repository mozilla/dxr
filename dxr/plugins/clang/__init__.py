"""C and CXX Plugin. (Currently relies on the clang compiler)"""

import os
import sys
from operator import itemgetter
from itertools import chain, izip, ifilter
from functools import partial

from funcy import (merge, imap, group_by, is_mapping, repeat, compose,
                   constantly)

from dxr import plugins
from dxr.plugins.clang.condense import load_csv, build_inheritance, call_graph
from dxr.plugins.needles import unsparsify_func
from dxr.plugins.clang.menu import (function_menu, variable_menu, type_menu,
                                    namespace_menu, namespace_alias_menu,
                                    macro_menu, include_menu)


PLUGIN_NAME = 'clang'

__all__ = [
    'FileToIndex',
    'TreeToIndex',
]


def jump_definition(tree, path, line):
    """ Add a jump to definition to the menu """
    url = '{0}/{1}/source/{2}#{3}'.format(
        tree.config.wwwroot, tree.name, path, line)

    return {
        'html':   "Jump to definition",
        'title':  "Jump to the definition in '%s'" % os.path.basename(path),
        'href':   url,
        'icon':   'jump'
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


class FileToIndex(plugins.FileToIndex):
    """C and CXX File Indexer using Clang Plugin."""
    def __init__(self, path, contents, tree, inherit):
        super(FileToIndex, self).__init__(path, contents, tree)
        self.inherit = inherit
        self.condensed = load_csv(*os.path.split(path))
        graph = call_graph(self.condensed, inherit)
        self._needles, self._needles_by_line = needles(self.condensed, inherit,
                                                       graph)

    def needles(self):
        return self._needles

    @unsparsify_func
    def needles_by_line(self):
        return self._needles_by_line

    @unsparsify_func
    def refs_by_line(self):
        """ Generate reference menus """
        # We'll need this argument for all queries here
        # Extents for functions defined here
        itemgetter2 = lambda x, y: compose(itemgetter(y), itemgetter(x))
        type_getter = lambda x: compose(chain, dict.values, itemgetter(x))
        return chain(
            self._common_ref(create_menu=function_menu,
                             view=itemgetter2('ref', 'function')),
            self._common_ref(create_menu=variable_menu,
                             view=itemgetter2('ref', 'variable')),
            self._common_ref(create_menu=type_menu,
                             view=type_getter('type')),
            self._common_ref(create_menu=type_menu,
                             view=type_getter('decldef')),
            self._common_ref(create_menu=type_menu,
                             view=itemgetter('typedefs')),
            self._common_ref(create_menu=namespace_menu,
                             view=itemgetter('namespace')),
            self._common_ref(create_menu=namespace_alias_menu,
                             view=itemgetter('namespace_aliases')),
            self._common_ref(create_menu=macro_menu,
                             view=itemgetter('macro'),
                             get_val=itemgetter('text')),
            self._common_ref(create_menu=include_menu,
                             view=itemgetter('include'))
        )

    @unsparsify_func
    def annotations_by_line(self):
        icon = "background-image: url('{0}/static/icons/warning.png');".format(
            self.tree.config.wwwroot)
        getter = itemgetter('msg', 'opt', 'span')
        for msg, opt, span in imap(getter, self.condensed['warnings']):
            if opt:
                msg = "{0}[{1}]".format(msg, opt)
            annotation = {
                'title': msg,
                'class': "note note-warning",
                'style': icon
            }
            yield annotation, span

    def _common_ref(self, create_menu, view, get_val=constantly(None)):
        for prop in view(self.condensed):
            start, end = prop['span']
            menu = create_menu(self.tree, prop)
            src, line, _ = start
            if src is not None:
                menu = jump_definition(self.tree, src, line) + menu
            yield (start, end, (menu, get_val(prop))), prop['span']

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

    :param name_key: key to access the name of a property.

    """
    names = (('c-{0}'.format(key.replace('_', '-')), props[name_key])
             for props in condensed[key] if name_key in props)
    return izip(names, spans(condensed, key))


def name_needles(condensed, key, ):
    """Return needles ((c-key, name), span).

    :param key: name of entry in condensed to get names from.

    """
    return chain(_name_needles(condensed, key, "name"),
                 _name_needles(condensed, key, "qualname"))


def spans(condensed, key):
    """Return list of spans from condensed.
    :arg key: name of entry in condensed to get spans from.
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


def walk_types(condensed):
    """Yield type, span of all types in analysis."""
    for key, vals in condensed.items():
        if is_mapping(vals):
            vals = vals.values()
        for val in vals:
            if 'type' in val and 'span' in val:
                yield str(val['type']), val['span']

    if 'type' in condensed:
        for vals in condensed['type'].values():
            for val in vals:
                yield val['name'], val['span']


def type_needles(condensed):
    """Return needles ((c-type, type), span)."""
    return ((('c-type', type_), span) for type_, span in walk_types(condensed))


def inherit_needles(condensed, tag, func):
    """Return list of needles ((c-tag, val), span).

    :type func: str -> iterable
    :param func: Map node name to an iterable of other node names.
    :param tag: First element in the needle tuple.

    """
    if isinstance(condensed['type'], list):
        return []
    children = (izip(func(c['name']), repeat(c['span'])) for c
                in condensed['type']['class'])

    return imap(lambda (a, (b, c)): ((a, b), c),
                izip(repeat('c-{0}'.format(tag)),
                     chain.from_iterable(children)))


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
            for func in condensed['function'] if name_key in func['override'])

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
    ))


class TreeToIndex(plugins.TreeToIndex):
    def __init__(self, tree):
        super(TreeToIndex, self).__init__(tree)
        self.tree = tree
        self._inherit, self._temp_folder = None, None

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
        self.inherit = build_inheritance(condensed)

    def file_to_index(self, path, contents):
        return FileToIndex(path, contents, self.tree, self._inherit)
