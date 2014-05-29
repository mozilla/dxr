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


# For each package in the plugins folder, go in there and


class DxrPlugin(object):
    def __init__(self, filters=None, indexer=None, htmlifier=None):
        self.filters = filters or []
        self.indexer = indexer
        self.htmlifier = htmlifier

    @classmethod
    def from_namespace(namespace):
        """Construct a DxrPlugin whose attrs are populated by typical naming
        and subclassing conventions.
        
        :arg namespace: A namespace from which to pick components

        Filters are taken to be any class whose name ends in "Filter" and
        doesn't start with "_".

        The indexer is assumed to be called "Indexer".

        If these rules don't suit you, you can always instantiate a DxrPlugin
        yourself (and think about refactoring this so separately expose the
        magic rules you *do* find useful.

        """
        ...
        return DxrPlugin(filters=[v for k, v in namespace.iteritems() if
                                  isclass(v) and
                                  not k.startswith('_') and
                                  k.endswith('Filter')],
                         indexer=namespace.get('Indexer'),
                     
        )


