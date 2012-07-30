import os, subprocess

def indexer_exports():
  """ Indexer files should export these, for use as __all__"""
  return ['pre_process', 'post_process']

def htmlifier_exports():
  """ Htmlifier files should export these, for use as __all__"""
  return ['htmlify']


def build_plugins(config):
  """ Build plugins, exit on failure """
  for plugin in config.enabled_plugins:
    path = os.path.join(config.plugin_folder, name)
    makefile = os.path.join(path, "makefile")
    if os.path.isfile(makefile):
      r = subprocess.call("make -f '%s' -j %i" % (makefile, config.nb_jobs),
                          cwd   = path,
                          shell = True)
      if r != 0:
        print >> sys.stderr, "Failed to build the '%s' plugin" % plugin
        sys.exit(1)


def load_indexers(tree):
  """ Load indexers for a given tree """
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
  plugins = []
  for name in tree.enabled_plugins:
    path = os.path.join(tree.config.plugin_folder, name)
    f, mod_path, desc = imp.find_module("htmlifier", [path])
    plugin = imp.load_module('dxr.plugins.' + name + "_htmlifier", f, mod_path, desc)
    f.close()
    plugins.append(plugin)
  return plugins


