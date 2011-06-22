import cPickle
from ConfigParser import ConfigParser
import imp
import os, sys
import string

###################
# Plugin handling #
###################

all_plugins = None
def get_active_plugins(tree=None, dxrsrc=None):
  """ Return all plugins that are used by the tree.
      If tree is None, then all usable plugins are returned. """
  global all_plugins
  if all_plugins is None:
    if dxrsrc is None and tree is not None:
      dxrsrc = tree.dxrroot
    all_plugins = load_plugins(dxrsrc)

  def plugin_filter(module):
    return module.can_use(tree)
  return filter(plugin_filter, all_plugins)

def load_plugins(dxrsrc=None):
  if dxrsrc is None:
    dxrsrc = os.path.realpath(os.path.dirname(sys.argv[0]))
  dirs = os.listdir(os.path.join(dxrsrc, 'xref-tools'))
  all_plugins = []
  for dirname in dirs:
    fullname = os.path.join(dxrsrc, 'xref-tools', dirname)
    try:
      m = imp.find_module('indexer', [fullname])
      module = imp.load_module('dxr.' + dirname, m[0], m[1], m[2])
      all_plugins.append(module)
    except:
      print "Unable to load plugin %s" % dirname
      print sys.exc_info()
      pass
  return all_plugins

def store_big_blob(tree, blob):
  htmlroot = os.path.join(tree.wwwdir, tree.tree + '-current')
  dbdir = os.path.join(htmlroot, '.dxr_xref')
  f = open(os.path.join(dbdir, 'index_blob.dat'), 'wb')
  try:
    cPickle.dump(blob, f, 2)
  finally:
    f.close()

def load_big_blob(tree):
  htmlroot = os.path.join(tree.wwwdir, tree.tree + '-current')
  dbdir = os.path.join(htmlroot, '.dxr_xref')
  f = open(os.path.join(dbdir, 'index_blob.dat'), 'rb')
  try:
    return cPickle.load(f)
  finally:
    f.close()

class DxrConfig(object):
  def __init__(self, config, tree=None):
    self._tree = tree
    self.templates = os.path.abspath(config.get('DXR', 'templates'))
    if config.has_option('DXR', 'dxrroot'):
      self.dxrroot = os.path.abspath(config.get('DXR', 'dxrroot'))
    else:
      self.dxrroot = None

    self.wwwdir = os.path.abspath(config.get('Web', 'wwwdir'))
    self.virtroot = os.path.abspath(config.get('Web', 'virtroot'))
    if self.virtroot.endswith('/'):
      self.virtroot = self.virtroot[:-1]
    self.hosturl = config.get('Web', 'hosturl')
    if not self.hosturl.endswith('/'):
      self.hosturl += '/'

    if tree is None:
      self.trees = []
      for section in config.sections():
        if section == 'DXR' or section == 'Web':
          continue
        self.trees.append(DxrConfig(config, section))
    else:
      self.tree = self._tree
      for opt in config.options(tree):
        self.__dict__[opt] = config.get(tree, opt)
        if opt.endswith('dir'):
          self.__dict__[opt] = os.path.abspath(self.__dict__[opt])
      if not 'dbdir' in self.__dict__:
        # Build the dbdir from [wwwdir]/tree
        self.dbdir = os.path.join(self.wwwdir, tree + '-current', '.dxr_xref')
      self.isdblive = self.dbdir.startswith(self.wwwdir)

  def getTemplateFile(self, name):
    tmpl = readFile(os.path.join(self.templates, name))
    tmpl = string.Template(tmpl).safe_substitute(**self.__dict__)
    return tmpl

  def getFileList(self):
    """ Returns an iterator of (relative, absolute) paths for the tree. """
    exclusions = self.__dict__.get("exclusions", ".hg\n.git\nCVS\n.svn")
    exclusions = exclusions.split()
    for root, dirs, files in os.walk(self.sourcedir, True):
      # Get the relative path to the source dir
      relpath = os.path.relpath(root, self.sourcedir)
      if relpath == '.':
        relpath = ''
      for f in files:
        # XXX: cxx-clang hack
        if f.endswith(".csv"): continue
        relfname = os.path.join(relpath, f)
        if any([f == ex for ex in exclusions]):
          continue
        yield (relfname, os.path.join(self.sourcedir, relfname))
      for ex in exclusions:
        if ex in dirs:
          dirs.remove(ex)

def readFile(filename):
  try:
    fp = open(filename)
    try:
      return fp.read()
    finally:
      fp.close()
  except IOError:
    print('Error reading %s: %s' % (filename, sys.exc_info()[1]))
    return None

def load_config(path):
  config = ConfigParser()
  config.read(path)

  return DxrConfig(config)

__all__ = ['get_active_plugins', 'store_big_blob', 'load_big_blob',
  'load_config', 'readFile']
