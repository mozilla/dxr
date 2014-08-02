"""C and CXX Plugin. (Currently relies on the clang compiler)"""

import os
from operator import itemgetter
from itertools import chain, izip

from funcy import merge, imap, group_by, is_mapping

from dxr import plugins
from dxr.plugins.clang.condense import load_csv, build_inhertitance


PLUGIN_NAME = 'clang'


class FileToIndex(plugins.FileToIndex):
    def __init__(self, path, contents, tree, inherit):
        super(FileToIndex, self).__init__(path, contents, tree)
        self.inherit = inherit
        condensed = load_csv(*os.path.split(path))
        self.needles, self.needles_by_line = needles(condensed, inherit)
        self.refs_by_line = refs(condensed)
        self.annotations_by_line = annotations(condensed)

    def needles(self):
        return self.needles

    def needles_by_line(self):
        return self.needles_by_line

    def refs_by_line(self):
        return self.refs_by_line  # TODO: look at htmlify.py

    def annotations_by_line(self):
        return self.annotations_by_line  # TODO: look at htmlify.py


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


def group_sparse_needles(needles):
    """Return a pair of iterators (file_needles, line_needles)."""
    needles_ = group_by(lambda x: 'file' if x[1] is None else 'line', needles)
    return needles_['file'], needles_['line']


def get_needle(condensed, tag, key1, key2, field=None, prefix=''):
    if field is None:
        field = tag

    prefix = '{0}-'.format(prefix) if prefix else ''

    return ((prefix + tag, key1, key2) for key1, key2
            in pluck2(key1, key2, condensed[field]))


def name_needles(condensed, key):
    return izip((('c-{0}'.format(key.replace('_', '-')), props['name'])
                for props in condensed[key]), spans(condensed, key))


def spans(condensed, key):
    return imap(itemgetter('span'), condensed[key])


def warn_needles(condensed):
    return izip((('c-warning', props['msg']) for props
                 in condensed['warning']), spans(condensed, 'warning'))


def warn_op_needles(condensed):
    return izip((('c-warning-opt', props['opt']) for props
                 in condensed['warning']), spans(condensed, 'warning'))


def callee_needles(condensed):
    return ((('c-callee', call.callee[0]), call.callee[1]) for call
            in condensed['call'])


def caller_needles(condensed):
    return ((('c-called-by', call.caller[0]), call.caller[1]) for call
            in condensed['call'])


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


def needles(condensed, inherit):
    return group_sparse_needles(chain(*[
        name_needles(condensed, 'function'),
        name_needles(condensed, 'variable'),
        name_needles(condensed, 'typedef'),
        name_needles(condensed, 'macro'),
        name_needles(condensed, 'namespace'),
        name_needles(condensed, 'namespace_alias'),
        warn_needles(condensed),
        warn_op_needles(condensed),
        callee_needles(condensed),
        caller_needles(condensed),
    ]))


class TreeToIndex(plugins.TreeToIndex):
    def __init__(self, tree):
        self.tree = tree

    def environment(self, vars_):
        """Setup environment variables for inspecting clang as runtime

        We'll store all the havested metadata in the plugins temporary folder.

        """
        tree = self.tree
        temp_folder = os.path.join(tree.temp_folder, 'plugins', PLUGIN_NAME)
        self.temp_folder = temp_folder
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
        condensed = load_csv(self.temp_folder, fpath=None, only_impl=True)
        self.inherit = build_inhertitance(condensed)

    def file_to_index(self, path, contents):
        return FileToIndex(path, contents, self.tree, self.inherit)
