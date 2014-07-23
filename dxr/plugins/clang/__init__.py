"""Clang Plugin"""

import os

from functools import wraps
from funcy import merge, partial

from dxr.plugins import FileToIndex
from dxr.plugins.utils import StatefulTreeToIndex
from dxr.plugins.clang.condense import load_csv, build_inhertitance


PLUGIN_NAME = 'clang'


class ClangFileToIndex(FileToIndex):
    def __init__(self, path, contents, tree, inherit):
        super(ClangFileToIndex, self).__init__(path, contents, tree)
        self.inherit = inherit

    def needles(self):
        return []

    def needles_by_line(self):
        return []

    def refs_by_line(self):
        return []

    def regions_by_line(self):
        return []

    def annotations_by_line(self):
        return []


class ClangTreeToIndex(StatefulTreeToIndex):
    def __init__(self, tree):
        super(ClangTreeToIndex, self).__init__(tree, clang_indexer)


def clang_indexer(tree):
    vars_ = yield
    # ENV SETUP

    # Setup environment variables for inspecting clang as runtime
    # We'll store all the havested metadata in the plugins temporary folder.
    temp_folder = os.path.join(tree.temp_folder, 'plugins', PLUGIN_NAME)
    plugin_folder = os.path.join(tree.config.plugin_folder, PLUGIN_NAME)
    flags = [
        '-load', os.path.join(plugin_folder, 'libclang-index-plugin.so'),
        '-add-plugin', 'dxr-index',
        '-plugin-arg-dxr-index', tree.source_folder
    ]
    flags_str = ""
    for flag in flags:
        flags_str += ' -Xclang ' + flag
    env = {
        'CC': "clang %s" % flags_str,
        'CXX': "clang++ %s" % flags_str,
        'DXR_CLANG_FLAGS': flags_str,
        'DXR_CXX_CLANG_OBJECT_FOLDER': tree.object_folder,
        'DXR_CXX_CLANG_TEMP_FOLDER': temp_folder,
    }
    env['DXR_CC'] = env['CC']
    env['DXR_CXX'] = env['CXX']

    yield merge(vars_, env)
    # PREBUILD
    yield # BUILD STEP
    # POSTBUILD
    condensed = load_csv(temp_folder, fpath=None, only_impl=True)
    inherit = build_inhertitance(condensed)
    yield partial(ClangFileToIndex, inherit=inherit)
