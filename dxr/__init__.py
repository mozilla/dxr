import cPickle
import imp
import os, sys

###################
# Plugin handling #
###################

plugins = None
def get_active_plugins(tree=None):
  """ Return all plugins that are used by the tree.
      If tree is None, then all usable plugins are returned. """
  global plugins
  if plugins is None:
    plugins = load_plugins()
  # XXX: filter out the tree
  return plugins

def load_plugins():
  # XXX: discover and iterate over available plugins
  basedir = os.path.realpath(os.path.dirname(sys.argv[0]))
  m = imp.find_module('indexer', [os.path.join(basedir, 'xref-tools/cxx-clang')])
  module = imp.load_module('dxr.cxx-clang', m[0], m[1], m[2])
  plugins = [module]
  return plugins

def store_big_blob(dxrconfig, tree, blob):
  htmlroot = os.path.join(dxrconfig["wwwdir"], tree["tree"] + '-current')
  dbdir = os.path.join(htmlroot, '.dxr_xref')
  f = open(os.path.join(dbdir, 'index_blob.dat'), 'wb')
  try:
    cPickle.dump(blob, f, 2)
  finally:
    f.close()

def load_big_blob(dxrconfig, tree):
  htmlroot = os.path.join(dxrconfig["wwwdir"], tree["tree"] + '-current')
  dbdir = os.path.join(htmlroot, '.dxr_xref')
  f = open(os.path.join(dbdir, 'index_blob.dat'), 'rb')
  try:
    return cPickle.load(f)
  finally:
    f.close()

__all__ = ['get_active_plugins', 'store_big_blob', 'load_big_blob']
