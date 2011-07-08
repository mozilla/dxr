#!/usr/bin/env python

from multiprocessing import cpu_count
from multiprocessing.pool import ThreadPool as Pool
from itertools import chain
import os
import sys
import getopt
import subprocess
import dxr.htmlbuilders
import shutil
import dxr
import sqlite3
import string

# At this point in time, we've already compiled the entire build, so it is time
# to collect the data. This process can be viewed as a pipeline.
# 1. Each plugin post-processes the data according to its own design. The output
#    is returned as an opaque python object. We save this object off as pickled
#    data to ease HTML development, and as an SQL database for searching.
# 2. The post-processed data is combined with the database and then sent to
#    htmlifiers to produce the output data.
# Note that either of these stages can be individually disabled.

def usage():
    print """Usage: run-dxr.py [options]
Options:
  -h, --help                              Show help information.
  -f, --file    FILE                      Use FILE as config file (default is ./dxr.config).
  -t, --tree    TREE                      Indxe and Build only section TREE (default is all).
  -c, --create  [xref|html]               Create xref or html and index (default is all).
  -d, --debug   file                      Only generate HTML for the file."""

big_blob = None

def post_process(treeconfig):
  global big_blob
  big_blob = {}
  srcdir = treeconfig.sourcedir
  objdir = treeconfig.objdir
  for plugin in dxr.get_active_plugins(treeconfig):
    if 'post_process' in plugin.__all__:
      big_blob[plugin.__name__] = plugin.post_process(srcdir, objdir)
  return big_blob

def WriteOpenSearch(name, hosturl, virtroot, wwwdir):
  try:
    fp = open(os.path.join(wwwdir, 'opensearch-' + name + '.xml'), 'w')
    try:
      fp.write("""<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
 <ShortName>%s</ShortName>
 <Description>Search DXR %s</Description>
 <Tags>mozilla dxr %s</Tags>
 <Url type="text/html"
      template="%s%s/search.cgi?tree=%s&amp;string={searchTerms}"/>
</OpenSearchDescription>""" % (name[:16], name, name, hosturl, virtroot, name))
    finally:
      fp.close()
  except IOError:
    print('Error writing opensearchfile (%s): %s' % (name, sys.exc_info()[1]))
    return None

def async_toHTML(treeconfig, srcpath, dstfile):
  """Wrapper function to allow doing this async without an instance method."""
  try:
    dxr.htmlbuilders.make_html(srcpath, dstfile, treeconfig, big_blob)
  except Exception, e:
    print 'Error on file %s:' % srcpath
    import traceback
    traceback.print_exc()

def make_index(file_list, dbdir):
  # For ease of searching, we follow something akin to
  # <http://vocamus.net/dave/?p=138>. This means that we now spit out the whole
  # contents of the sourcedir into a single file... it makes grep very fast,
  # since we don't have the syscall penalties for opening and closing every
  # file.
  file_index = open(os.path.join(dbdir, "file_index.txt"), 'w')
  offset_index = open(os.path.join(dbdir, "index_index.txt"), 'w')
  for fname in file_list:
    offset_index.write('%s:%d\n' % (fname[0], file_index.tell()))
    f = open(fname[1], 'r')
    lineno = 1
    for line in f:
      if len(line.strip()) > 0:
        file_index.write(fname[0] + ":" + str(lineno) + ":" + line)
      lineno += 1
    if line[-1] != '\n':
      file_index.write('\n');
    f.close()
  offset_index.close()
  file_index.close()

def builddb(treecfg, dbdir):
  """ Post-process the build and make the SQL directory """
  print "Post-processing the source files..."
  big_blob = post_process(treecfg)
  print "Storing data..."
  dxr.store_big_blob(treecfg, big_blob)

  print "Building SQL..."
  all_statements = []
  schemata = []
  for plugin in dxr.get_active_plugins(treecfg):
    schemata.append(plugin.get_schema())
    if plugin.__name__ in big_blob:
      all_statements.extend(plugin.sqlify(big_blob[plugin.__name__]))

  dbname = treecfg.tree + '.sqlite'
  conn = sqlite3.connect(os.path.join(dbdir, dbname))
  conn.executescript('\n'.join(schemata))
  conn.commit()
  for stmt in all_statements:
    if isinstance(stmt, tuple):
      conn.execute(stmt[0], stmt[1])
    else:
      conn.execute(stmt)
  conn.commit()
  conn.close()

def indextree(treecfg, doxref, dohtml, debugfile):
  global big_blob

  # If we're live, we'll need to move -current to -old; we'll move it back
  # after we're done.
  if treecfg.isdblive:
    currentroot = os.path.join(treecfg.wwwdir, treecfg.tree + '-current')
    oldroot = os.path.join(treecfg.wwwdir, treecfg.tree + '-old')
    linkroot = os.path.join(treecfg.wwwdir, treecfg.tree)
    if os.path.isdir(currentroot):
      if os.path.exists(os.path.join(currentroot, '.dxr_xref', '.success')):
        # Move current -> old, change link to old
        try:
          shutil.rmtree(oldroot)
        except OSError:
          pass
        try:
          shutil.move(currentroot, oldroot)
          os.unlink(linkroot)
          os.symlink(oldroot, linkroot)
        except OSError:
          pass
      else:
        # This current directory is bad, move it away
        shutil.rmtree(currentroot)

  # dxr xref files (index + sqlitedb) go in wwwdir/treename-current/.dxr_xref
  # and we'll symlink it to wwwdir/treename later
  htmlroot = os.path.join(treecfg.wwwdir, treecfg.tree + '-current')
  dbdir = os.path.join(htmlroot, '.dxr_xref')
  os.makedirs(dbdir, 0755)
  dbname = treecfg.tree + '.sqlite'

  retcode = 0
  if doxref:
    builddb(treecfg, dbdir)
    if treecfg.isdblive:
      f = open(os.path.join(dbdir, '.success'), 'w')
      f.close()
  elif treecfg.isdblive:
    # If the database is live, we need to copy database info from the old
    # version of the code
    oldhtml = os.path.join(treecfg.wwwdir, treecfg.tree + '-old')
    olddbdir = os.path.join(oldhtml, '.dxr_xref')
    shutil.rmtree(dbdir)
    shutil.copytree(olddbdir, dbdir)

  # Build static html
  if dohtml:
    if not doxref:
      big_blob = dxr.load_big_blob(treecfg)
    dxr.htmlbuilders.build_htmlifier_map(dxr.get_active_plugins(treecfg))
    treecfg.database = os.path.join(dbdir, dbname)

    n = cpu_count()
    p = Pool(processes=n)

    print 'Building HTML files for %s...' % treecfg.tree

    debug = (debugfile is not None)

    index_list = open(os.path.join(dbdir, "file_list.txt"), 'w')
    file_list = []

    def getOutputFiles():
      for regular in treecfg.getFileList():
        yield regular
      filelist = set()
      for plug in big_blob:
        try:
          filelist.update(big_blob[plug]["byfile"].keys())
        except KeyError:
          pass
      for filename in filelist:
        if filename.startswith("--GENERATED--/"):
          relpath = filename[len("--GENERATED--/"):]
          yield filename, os.path.join(treecfg.objdir, relpath)

    for f in getOutputFiles():
      # In debug mode, we only care about some files
      if debugfile is not None and f[0] != debugfile: continue

      index_list.write(f[0] + '\n')
      cpypath = os.path.join(htmlroot, f[0])
      srcpath = f[1]
      file_list.append(f)

      # Make output directory
      cpydir = os.path.dirname(cpypath)
      if not os.path.exists(cpydir):
        os.makedirs(cpydir)

      p.apply_async(async_toHTML, [treecfg, srcpath, cpypath + ".html"])

    p.apply_async(make_index, [file_list, dbdir])

    index_list.close()
    p.close()
    p.join()

  # If the database is live, we need to switch the live to the new version
  if treecfg.isdblive:
    try:
      os.unlink(linkroot)
      shutil.rmtree(oldroot)
    except OSError:
      pass
    os.symlink(currentroot, linkroot)

def parseconfig(filename, doxref, dohtml, tree, debugfile):
  # Build the contents of an html <select> and open search links
  # for all trees encountered.
  options = ''
  opensearch = ''

  dxrconfig = dxr.load_config(filename)

  for treecfg in dxrconfig.trees:
    # if tree is set, only index/build this section if it matches
    if tree and treecfg.tree != tree:
        continue

    options += '<option value="' + treecfg.tree + '">' + treecfg.tree + '</option>'
    opensearch += '<link rel="search" href="opensearch-' + treecfg.tree + '.xml" type="application/opensearchdescription+xml" '
    opensearch += 'title="' + treecfg.tree + '" />\n'
    WriteOpenSearch(treecfg.tree, treecfg.hosturl, treecfg.virtroot, treecfg.wwwdir)
    indextree(treecfg, doxref, dohtml, debugfile)

  # Generate index page with drop-down + opensearch links for all trees
  indexhtml = dxrconfig.getTemplateFile('dxr-index-template.html')
  indexhtml = string.Template(indexhtml).safe_substitute(**treecfg.__dict__)
  indexhtml = indexhtml.replace('$OPTIONS', options)
  indexhtml = indexhtml.replace('$OPENSEARCH', opensearch)
  index = open(os.path.join(dxrconfig.wwwdir, 'index.html'), 'w')
  index.write(indexhtml)
  index.close()


def main(argv):
  configfile = './dxr.config'
  doxref = True
  dohtml = True
  tree = None
  debugfile = None

  try:
    opts, args = getopt.getopt(argv, "hc:f:t:d:",
        ["help", "create=", "file=", "tree=", "debug="])
  except getopt.GetoptError:
    usage()
    sys.exit(2)

  for a, o in opts:
    if a in ('-f', '--file'):
      configfile = o
    elif a in ('-c', '--create'):
      if o == 'xref':
        dohtml = False
      elif o == 'html':
        doxref = False
    elif a in ('-h', '--help'):
      usage()
      sys.exit(0)
    elif a in ('-t', '--tree'):
      tree = o
    elif a in ('-d', '--debug'):
      debugfile = o

  parseconfig(configfile, doxref, dohtml, tree, debugfile)

if __name__ == '__main__':
  main(sys.argv[1:])
