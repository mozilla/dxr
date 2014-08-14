"""C and CXX Plugin. (Currently relies on the clang compiler)"""

import os
from operator import itemgetter
from itertools import chain, izip

from funcy import merge, imap, group_by, is_mapping, repeat

from dxr import plugins
from dxr.plugins.clang.condense import load_csv, build_inheritance, call_graph


PLUGIN_NAME = 'clang'

__all__ = [
    'FileToIndex',
    'TreeToIndex',
]


class FileToIndex(plugins.FileToIndex):
    """C and CXX File Indexer using Clang Plugin."""
    def __init__(self, path, contents, tree, inherit):
        super(FileToIndex, self).__init__(path, contents, tree)
        self.inherit = inherit
        condensed = load_csv(*os.path.split(path))
        graph = call_graph(condensed, inherit)
        self._needles, self._needles_by_line = needles(condensed, inherit,
                                                       graph)
        self._refs_by_line = refs(condensed)
        self._annotations_by_line = annotations(condensed)

    def needles(self):
        return self._needles

    def needles_by_line(self):
        return self._needles_by_line

    def refs_by_line(self):
        return self._refs_by_line  # TODO: look at htmlify.py

    def annotations_by_line(self):
        return self._annotations_by_line  # TODO: look at htmlify.py


def refs(_):
    return []


def annotations(_):
    return []


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


def name_needles(condensed, key):
    """Return a list of needles ((c-key, name), span).

    :param key: name of entry in condensed to get names from.
    """
    return izip((('c-{0}'.format(key.replace('_', '-')), props['name'])
                 for props in condensed[key]), spans(condensed, key))


def spans(condensed, key):
    """Return list of spans from condensed.

    :arg key: name of entry in condensed to get spans from.
    """
    return imap(itemgetter('span'), condensed[key])


def warn_needles(condensed):
    """Return list of needles (('c-warning', msg), span)."""
    return izip((('c-warning', props['msg']) for props
                 in condensed['warning']), spans(condensed, 'warning'))


def warn_op_needles(condensed):
    """Return list of needles (('c-warning-opt', opt), span)."""
    return izip((('c-warning-opt', props['opt']) for props
                 in condensed['warning']), spans(condensed, 'warning'))


def callee_needles(graph):
    """Return list of needles (('c-callee', callee name), span)."""
    return ((('c-callee', call.callee[0]), call.callee[1]) for call
            in graph)


def caller_needles(graph):
    """Return list of needles (('c-needle', caller name), span)."""
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
    """Return list of needles representing subclass relationships.

    :type inherit: mapping parent:str -> Set child:str

    """
    return inherit_needles(condensed, 'child',
                            lambda name: inherit.get(name, []))


def parent_needles(condensed, inherit):
    """Return list of needles representing super class relationships.

    :type inherit: mapping parent:str -> Set child:str

    """
    def get_parents(name):
        return (parent for parent, children in inherit.items()
                if name in children)

    return inherit_needles(condensed, 'parent', get_parents)


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
        self._inherit = build_inheritance(condensed)

    def file_to_index(self, path, contents):
        return FileToIndex(path, contents, self.tree, self._inherit)
