"""C and CXX Plugin. (Currently relies on the clang compiler)"""

import os
from operator import itemgetter
from itertools import chain, izip

from funcy import merge, partial, imap, group_by
from dxr.plugins import FileToIndex as FTI, TreeToIndex as TTI
from dxr.plugins.clang.condense import load_csv, build_inhertitance


PLUGIN_NAME = 'clang'


class FileToIndex(FTI):
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
        return self.refs_by_line # TODO: look at htmlify.py

    def annotations_by_line(self):
        return self.annotations_by_line # TODO: look at htmlify.py


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


def default_needles(condensed, key):
    return izip((('c-{0}'.format(key.replace('_', '-')), props['name'])
                for props in condensed[key]), spans(condensed, key))


def spans(condensed, key):
    return imap(itemgetter('span'), condensed[key])


def warn_needles(condensed):
    return izip((('c-warning', props['msg']) for props in condensed['warning']),
                spans(condensed, 'warning'))


def warn_op_needles(condensed):
    return izip((('c-warning-opt', props['opt']) for props in condensed['warning']),
                spans(condensed, 'warning'))


def callee_needles(condensed):
    return ((('c-callee', call.callee[0]), call.callee[1]) for call
            in condensed['call'])


def caller_needles(condensed):
    return ((('c-called-by', call.caller[0]), call.caller[1]) for call
            in condensed['call'])


def needles(condensed, inherit):
    return group_sparse_needles(chain(*[
        default_needles(condensed, 'function'),
        default_needles(condensed, 'variable'),
        default_needles(condensed, 'typedef'),
        default_needles(condensed, 'macro'),
        default_needles(condensed, 'namespace'),
        default_needles(condensed, 'namespace_alias'),
        warn_needles(condensed),
        warn_op_needles(condensed),
        callee_needles(condensed),
        caller_needles(condensed),
    ]))


class TreeToIndex(TTI):
    def __init__(self, tree):
        self.tree = tree
    
    def environment(self, vars_):    # Setup environment variables for inspecting clang as runtime
        # We'll store all the havested metadata in the plugins temporary folder.
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



