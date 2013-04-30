import os, sys
import imp


def indexer_exports():
    """ Indexer files should export these, for use as __all__"""
    return ['pre_process', 'post_process']


def htmlifier_exports():
    """ Htmlifier files should export these, for use as __all__"""
    return ['htmlify', 'load']


def load_indexers(tree):
    """ Load indexers for a given tree """
    # Allow plugins to load from the plugin folder
    sys.path.append(tree.config.plugin_folder)
    plugins = []
    for name in tree.enabled_plugins:
        path = os.path.join(tree.config.plugin_folder, name)
        f, mod_path, desc = imp.find_module("indexer", [path])
        plugin = imp.load_module('dxr.plugins.' + name + "_indexer", f, mod_path, desc)
        f.close()
        plugins.append(plugin)
    return plugins


def load_htmlifiers(tree):
    """ Load htmlifiers for a given tree """
    # Allow plugins to load from the plugin folder
    sys.path.append(tree.config.plugin_folder)
    plugins = []
    for name in tree.enabled_plugins:
        path = os.path.join(tree.config.plugin_folder, name)
        f, mod_path, desc = imp.find_module("htmlifier", [path])
        plugin = imp.load_module('dxr.plugins.' + name + "_htmlifier", f, mod_path, desc)
        f.close()
        plugins.append(plugin)
    return plugins
