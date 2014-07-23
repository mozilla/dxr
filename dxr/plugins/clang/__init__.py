"""Clang Plugin"""

import os

from functools import wraps
from funcy import merge, partial, decorator

from dxr.plugins import TreeToIndex
from dxr.plugins.clang.condense import load_csv, build_inhertitance

PLUGIN_NAME = 'clang'

class CXXTreeToIndex(TreeToIndex):
    """Clang TreeToIndexer instance."""
    def environment(self, vars_):
        # Setup environment variables for inspecting clang as runtime
        # We'll store all the havested metadata in the plugins temporary folder.
        tree = self.tree
        self.temp_folder = os.path.join(tree.temp_folder, 'plugins', PLUGIN_NAME)
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
            'DXR_CXX_CLANG_TEMP_FOLDER': self.temp_folder,
        }
        env['DXR_CC'] = env['CC']
        env['DXR_CXX'] = env['CXX']
        
        return merge(vars_, env)

        
    def post_build(self):
        condensed = load_csv(self.temp_folder, csv_path=None, only_impl=True)
        self.inherit = build_inhertitance(condensed)


    def file_to_index(self, path, contents):
        return ClangFileToIndex(path, contents, self.tree, self.inherit)


@decorator
def transition(call, start, end):
    self = call._args[0]
    if self.state != start:
        raise RuntimeError('In state {0}, expected {1}'.format(
            self.state, start))
    out = call()
    self.state = end
    return out

class StatefulTreeToIndex(TreeToIndex):
    def __init__(tree, state_machine):
        super(StatefulTreeToIndex, self).__init__(tree)
        self.state_machine = state_machine()
        next(self.state_machine)
        self.state = "start"
        

    @transition('start', 'environment')
    def environment(self, vars):
        self.state_machine.send(vars)
        return next(self.state_machine)

    @transition('environment', 'pre_build')
    def pre_build(self):
        next(self.state_machine)


    @transition('pre_build', 'post_build')
    def post_build(self):
        self.file_indexer = next(self.state_machine)

    @transition('post_build', 'post_build')
    def file_to_index(self, path, contents):
        return self.file_indexer(path, contents)


class ClangFileToIndex(File_To_Index):
    pass # ClangFileToIndex definition


def env(vars_, tree):
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

    return merge(vars_, env)


@tree_to_indexer # Creates TreeIndexer
def clang_indexer(tree):
    vars_ = yield
    # Env setup
    yield env(vars_, tree)

    # PREBUILD

    yield # BUILD STEP
    
    # POST BUILD

    # Build up only the inheritance part of the CSV
    condensed = load_csv(temp_folder, csv_path=None, only_impl=True)
    inherit = build_inhertitance(condensed)

    yield partial(ClangFileToIndex, inherit)
