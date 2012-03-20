#!/usr/bin/env python

from multiprocessing import cpu_count
from multiprocessing.pool import ThreadPool as Pool
from itertools import chain
import dxr
import dxr.htmlbuilders
import dxr.languages
import getopt
import glob
import os
import shutil
import sqlite3
import string
import subprocess
import sys
import time
import ctypes
import tempfile

# At this point in time, we've already compiled the entire build, so it is time
# to collect the data. This process can be viewed as a pipeline.
# 1. Each plugin post-processes the data according to its own design. The output
#    is returned as an opaque python object. We save this object off as pickled
#    data to ease HTML development, and as an SQL database for searching.
# 2. The post-processed data is combined with the database and then sent to
#    htmlifiers to produce the output data.
# Note that either of these stages can be individually disabled.

def usage():
    print """Usage: dxr-index.py [options]
Options:
  -h, --help                              Show help information.
  -f, --file    FILE                      Use FILE as config file (default is ./dxr.config).
  -t, --tree    TREE                      Index and Build only section TREE (default is all).
  -c, --create  [xref|html]               Create xref or html and index (default is all).
  -d, --debug   glob                      Only generate HTML for the file(s)."""

big_blob = None

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

def make_index(file_list, dbdir, treecfg):
  conn = getdbconn(treecfg, dbdir)

  conn.execute('DROP TABLE IF EXISTS fts')
  conn.execute('CREATE VIRTUAL TABLE fts USING fts4 (basename, content, tokenize=dxrCodeTokenizer)')

  conn.execute('DROP TABLE IF EXISTS files')
  conn.execute('CREATE TABLE files (ID INTEGER PRIMARY KEY, path VARCHAR(1024))')

  conn.execute('CREATE INDEX IF NOT EXISTS files_index ON files (path)')

  cur = conn.cursor();

  for fname in file_list:
    try:
      f = open(fname[1], 'r')

      cur.execute('INSERT INTO fts (basename,content) VALUES (?, ?)', (os.path.basename (fname[0]), f.read ()))
      cur.execute('INSERT INTO files (id, path) VALUES (?, ?)', (cur.lastrowid, fname[0]))
      f.close()

      if cur.lastrowid % 100 == 0:
        conn.commit()
    except:
      print "Error inserting FTS for file '%s': %s" % (fname[0], sys.exc_info()[1])

  cur.close()
  conn.commit()
  conn.close()


def make_index_html(treecfg, dirname, fnames, htmlroot):
  genroot = os.path.relpath(dirname, htmlroot)
  if genroot.startswith('./'): genroot = genroot[2:]
  if genroot.startswith('--GENERATED--'):
    srcpath = treecfg.objdir
    genroot = genroot[len("--GENERATED--") + 1:]
  else:
    srcpath = treecfg.sourcedir
  srcpath = os.path.join(srcpath, genroot)
  of = open(os.path.join(dirname, 'index.html'), 'w')
  try:
    html_header = treecfg.getTemplateFile("dxr-header.html")
    of.write(html_header.replace('${sidebarActions}', '\n'))
    of.write('''<div id="maincontent" dojoType="dijit.layout.ContentPane"
      region="center"><table id="index-list">
        <tr><th></th><th>Name</th><th>Last modified</th><th>Size</th></tr>
      ''')
    of.write('<tr><td><img src="%s/images/icons/folder.png"></td>' %
      treecfg.virtroot)
    of.write('<td><a href="..">Parent directory</a></td>')
    of.write('<td></td><td>-</td></tr>')
    torm = []
    fnames.sort()
    dirs, files = [], []
    for fname in fnames:
      # Ignore hidden files
      if fname[0] == '.':
        torm.append(fname)
        continue
      fullname = os.path.join(dirname, fname)

      # Directory ?
      if os.path.isdir(fullname):
        img = 'folder.png'
        link = fname
        display = fname + '/'
        if fname == '--GENERATED--':
          stat = os.stat(treecfg.objdir) # Meh, good enough
        else:
          stat = os.stat(os.path.join(srcpath, fname))
        size = '-'
        add = dirs
      else:
        img = 'page_white.png'
        link = fname
        display = fname[:-5] # Remove .html
        stat = os.stat(os.path.join(srcpath, display))
        size = stat.st_size
        if size > 2 ** 30:
          size = str(size / 2 ** 30) + 'G'
        elif size > 2 ** 20:
          size = str(size / 2 ** 20) + 'M'
        elif size > 2 ** 10:
          size = str(size / 2 ** 10) + 'K'
        else:
          size = str(size)
        add = files
      add.append('<tr><td><img src="%s/images/icons/%s"></td>' %
        (treecfg.virtroot, img))
      add.append('<td><a href="%s">%s</a></td>' % (link, display))
      add.append('<td>%s</td><td>%s</td>' % (
        time.strftime('%Y-%b-%d %H:%m', time.gmtime(stat.st_mtime)), size))
      add.append('</tr>')
    of.write(''.join(dirs))
    of.write(''.join(files))
    of.flush()
    of.write(treecfg.getTemplateFile("dxr-footer.html"))

    for f in torm:
      fnames.remove(f)
  except:
    sys.excepthook(*sys.exc_info())
  finally:
    of.close()

def getdbconn(treecfg, dbdir):
  dbname = treecfg.tree + '.sqlite'
  conn = sqlite3.connect(os.path.join(dbdir, dbname))
  conn.execute('PRAGMA synchronous=off')
  conn.execute('PRAGMA page_size=65536')
  # Safeguard against non-ASCII text. Let's just hope everyone uses UTF-8
  conn.text_factory = str

  # Initialize code tokenizer
  conn.execute('SELECT initialize_tokenizer()')

  return conn


def builddb(treecfg, dbdir, tmproot):
  """ Post-process the build and make the SQL directory """
  global big_blob

  # We use this all over the place, cache it here.
  plugins = dxr.get_active_plugins(treecfg)

  # Building the database--this happens as multiple phases. In the first phase,
  # we basically collect all of the information and organizes it. In the second
  # phase, we link the data across multiple languages.
  print "Post-processing the source files..."
  big_blob = {}
  srcdir = treecfg.sourcedir
  objdir = treecfg.objdir
  for plugin in plugins:
    if 'post_process' in plugin.__all__:
      big_blob[plugin.__name__] = plugin.post_process(srcdir, objdir)

  # Save off the raw data blob
  print "Storing data..."
  dxr.store_big_blob(treecfg, big_blob, tmproot)

  # Build the sql for later queries. This is a combination of the main language
  # schema as well as plugin-specific information. The pragmas that are
  # executed should make the sql stage go faster.
  print "Building SQL..."
  conn = getdbconn(treecfg, dbdir)

  # Import the schemata
  schemata = [dxr.languages.get_standard_schema()]
  for plugin in plugins:
    schemata.append(plugin.get_schema())
  conn.executescript('\n'.join(schemata))
  conn.commit()

  # Load and run the SQL
  def sql_generator():
    for statement in dxr.languages.get_sql_statements():
      yield statement
    for plugin in plugins:
      if plugin.__name__ in big_blob:
        plugblob = big_blob[plugin.__name__]
        for statement in plugin.sqlify(plugblob):
          yield statement

  for stmt in sql_generator():
    if isinstance(stmt, tuple):
      conn.execute(stmt[0], stmt[1])
    else:
      conn.execute(stmt)
  conn.commit()
  conn.close()

def indextree(treecfg, doxref, dohtml, debugfile):
  global big_blob

  # dxr xref files (index + sqlitedb) go in wwwdir/treename-current/.dxr_xref
  # and we'll symlink it to wwwdir/treename later
  htmlroot = os.path.join(treecfg.wwwdir, treecfg.tree + '-current')
  oldroot = os.path.join(treecfg.wwwdir, treecfg.tree + '-old')
  tmproot = tempfile.mkdtemp(prefix = (os.path.join(treecfg.wwwdir, '.' + treecfg.tree + '.')))
  linkroot = os.path.join(treecfg.wwwdir, treecfg.tree)

  dbdir = os.path.join(tmproot, '.dxr_xref')
  os.makedirs(dbdir, 0755)
  dbname = treecfg.tree + '.sqlite'

  retcode = 0
  if doxref:
    builddb(treecfg, dbdir, tmproot)

  # Build static html
  if dohtml:
    if not doxref:
      big_blob = dxr.load_big_blob(treecfg, tmproot)
    # Do we need to do file pivoting?
    for plugin in dxr.get_active_plugins(treecfg):
      if plugin.__name__ in big_blob:
        plugin.pre_html_process(treecfg, big_blob[plugin.__name__])
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

    if debugfile:
      output_files = glob.glob (treecfg.sourcedir + '/' + debugfile)
      if output_files == []:
        print 'Error: Glob %s doesn\'t match any files' % debugfile
        sys.exit (1)
    last_dir = None

    for f in getOutputFiles():
      # In debug mode, we only care about some files
      if debugfile and not treecfg.sourcedir + '/' + f[0] in output_files: continue

      index_list.write(f[0] + '\n')
      cpypath = os.path.join(tmproot, f[0])
      srcpath = f[1]
      file_list.append(f)

      # Make output directory
      cpydir = os.path.dirname(cpypath)
      if not os.path.exists(cpydir):
        os.makedirs(cpydir)

      def is_text(srcpath):
        # xdg.Mime considers .lo as text, which is technically true but useless
        if srcpath[-3:] == '.lo': return False
        import xdg.Mime
        mimetype = str(xdg.Mime.get_type (srcpath))
        for valid in ['text', 'xml', 'shellscript', 'perl', 'm4', 'xbel', 'javascript']:
          if valid in mimetype:
            return True
        return False
      if not is_text(srcpath):
        continue
      p.apply_async(async_toHTML, [treecfg, srcpath, cpypath + ".html"])

    if file_list == []:
        print 'Error: No files found to index'
        sys.exit (0)

    p.apply_async(make_index, [file_list, dbdir, treecfg])

    index_list.close()
    p.close()
    p.join()

    # Generate index.html files
    # XXX: This wants to be parallelized. However, I seem to run into problems
    # if it isn't.
    def genhtml(treecfg, dirname, fnames):
      make_index_html(treecfg, dirname, fnames, tmproot)
    os.path.walk(tmproot, genhtml, treecfg)

  if os.path.exists(oldroot):
    shutil.rmtree(oldroot)

  if os.path.exists(htmlroot):
    shutil.move(htmlroot, oldroot)

  os.chmod(tmproot, 0755)
  shutil.move(tmproot, htmlroot)

  try:
    os.unlink(linkroot)
    os.symlink(htmlroot, linkroot)
  except:
    pass

def parseconfig(filename, doxref, dohtml, tree, debugfile):
  # Build the contents of an html <select> and open search links
  # for all trees encountered.
  # Note: id for CSS, name for form "get" value in query
  browsetree = ''
  options = '<select id="tree" name="tree">'
  opensearch = ''

  dxrconfig = dxr.load_config(filename)

  for treecfg in dxrconfig.trees:
    # if tree is set, only index/build this section if it matches
    if tree and treecfg.tree != tree:
        continue

    treecfg.virtroot = dxrconfig.virtroot
    browsetree += '<a href="%s">Browse <b>%s</b> source</a> ' % (treecfg.tree, treecfg.tree)
    options += '<option value="' + treecfg.tree + '">' + treecfg.tree + '</option>'
    opensearch += '<link rel="search" href="opensearch-' + treecfg.tree + '.xml" type="application/opensearchdescription+xml" '
    opensearch += 'title="' + treecfg.tree + '" />\n'
    WriteOpenSearch(treecfg.tree, treecfg.hosturl, treecfg.virtroot, treecfg.wwwdir)
    indextree(treecfg, doxref, dohtml, debugfile)

  # Generate index page with drop-down + opensearch links for all trees
  indexhtml = dxrconfig.getTemplateFile('dxr-index-template.html')
  indexhtml = string.Template(indexhtml).safe_substitute(**treecfg.__dict__)
  indexhtml = indexhtml.replace('$BROWSETREE', browsetree)
  if len(dxrconfig.trees) > 1:
    options += '</select>'
  else:
    options = '<input type="hidden" id="tree" value="' + treecfg.tree + '">'
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
    if os.getenv("DXRSRC") is not None:
      dll_base = os.getenv("DXRSRC")
    else:
      dll_base = os.path.dirname(sys.argv[0])

    dll_path = os.path.join(dll_base, "sqlite", "libdxr-code-tokenizer.so")
    ctypes_init_tokenizer = ctypes.CDLL(dll_path).dxr_code_tokenizer_init
    ctypes_init_tokenizer()
  except:
    msg = sys.exc_info()[1] # Python 2/3 compatibility
    print "Could not load tokenizer: %s" % msg
    sys.exit(2)

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
