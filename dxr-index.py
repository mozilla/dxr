#!/usr/bin/env python

from multiprocessing import Pool, cpu_count
import imp
import os
import sys
import getopt
import subprocess
#import generic2html
#import idl2html #, cpp2html
sys.path.append("./xref-scripts")
import dxr.htmlbuilders
import shutil
import dxr_config
import template
import dxr
import string

# At this point in time, we've already compiled the entire build, so it is time
# to collect the data. This process can be viewed as a pipeline.
# 1. Each plugin post-processes the data according to its own design. The output
#    is returned as an opaque python object. We save this object off as pickled
#    data to ease HTML development.
# 2. We convert the post-processed data into the output xref database.
# 3. The post-processed data is combined with the database and then sent to
#    htmlifiers to produce the output data.
# Note that each of these stages can be individually disabled.

def usage():
    print """Usage: run-dxr.py [options]
Options:
  -h, --help                              Show help information.
  -f, --file    FILE                      Use FILE as config file (default is ./dxr.config).
  -t, --tree    TREE                      Indxe and Build only section TREE (default is all).
  -c, --create  [xref|html]               Create xref or html and glimpse index (default is all).
  -d, --debug   file                      Only generate HTML for the file."""

big_blob = None

def post_process(dxrconfig, treeconfig):
  global big_blob
  big_blob = {}
  srcdir = treeconfig['sourcedir']
  objdir = treeconfig['objdir']
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
      template="%s/%s/search.cgi?tree=%s&amp;string={searchTerms}"/>
</OpenSearchDescription>""" % (name[:16], name, name, hosturl, virtroot, name))
    finally:
      fp.close()
  except IOError:
    print('Error writing opensearchfile (%s): %s' % (name, sys.exc_info()[1]))
    return None

def async_toHTML(dxrconfig, treeconfig, srcpath, newroot):
  """Wrapper function to allow doing this async without an instance method."""
  htmlBuilder = None
  if os.path.splitext(srcpath)[1] in ['.h', '.c', '.cpp', '.m', '.mm']:
    htmlBuilder = dxr.htmlbuilders.CppHtmlBuilder(dxrconfig, treeconfig, srcpath, newroot, big_blob['dxr.cxx-clang'])
  elif os.path.splitext(srcpath)[1] == '.idl':
    htmlBuilder = dxr.htmlbuilders.IdlHtmlBuilder(dxrconfig, treeconfig, srcpath, newroot)
  else:
    htmlBuilder = dxr.htmlbuilders.HtmlBuilderBase(dxrconfig, treeconfig, srcpath, newroot)

  try:
    htmlBuilder.toHTML()
  except Exception, e:
    print str(e)
    import traceback
    traceback.print_exc()


def indextree(dxrconfig, treeconfig, doxref, dohtml, debugfile):
  global big_blob
  # dxr xref files (glimpse + sqlitedb) go in wwwdir/treename-current/.dxr_xref
  # and we'll symlink it to wwwdir/treename later
  htmlroot = os.path.join(dxrconfig["wwwdir"], treeconfig["tree"] + '-current')
  dbdir = os.path.join(htmlroot, '.dxr_xref')
  dbname = treeconfig["tree"] + '.sqlite'

  retcode = 0
  if doxref:
    # Build the blob, and make the sql
    post_process(dxrconfig, treeconfig)
    for plugin in dxr.get_active_plugins(treeconfig):
      if plugin.__name__ in big_blob:
        f = open(os.path.join(treeconfig["objdir"], plugin.__name__ + ".sql"), 'w')
        try:
          f.write(plugin.sqlify(big_blob[plugin.__name__]));
        finally:
          f.close()
    # Build dxr.sqlite
    buildxref = os.path.join(dxrconfig["xrefscripts"], "build-xref.sh")
    retcode = subprocess.call([buildxref, treeconfig["sourcedir"], treeconfig["objdir"],
                              treeconfig["mozconfig"], dxrconfig["xrefscripts"], dbdir, dbname,
                              dxrconfig["wwwdir"], treeconfig["tree"]])
    dxr.store_big_blob(dxrconfig, treeconfig, big_blob)
    if retcode != 0:
        return

  # Build static html
  if dohtml:
    big_blob = dxr.load_big_blob(dxrconfig, treeconfig)
    buildhtml = os.path.join(dxrconfig["xrefscripts"], "build-html.sh")
    dxrconfig["html_header"] = os.path.join(dxrconfig["templates"], "dxr-header.html")
    dxrconfig["html_footer"] = os.path.join(dxrconfig["templates"], "dxr-footer.html")
    dxrconfig["html_sidebar_header"] = os.path.join(dxrconfig["templates"], "dxr-sidebar-header.html")
    dxrconfig["html_sidebar_footer"] = os.path.join(dxrconfig["templates"], "dxr-sidebar-footer.html")
    dxrconfig["html_main_header"] = os.path.join(dxrconfig["templates"], "dxr-main-header.html")
    dxrconfig["html_main_footer"] = os.path.join(dxrconfig["templates"], "dxr-main-footer.html")
    dxrconfig["database"] = os.path.join(dbdir, dbname)
#    dxrsqlite = os.path.join(dbdir, dbname)

    n = cpu_count()
    p = Pool(processes=n)

    print 'Building HTML files for %s...' % treeconfig["tree"]

    debug = (debugfile is not None)

    for root, dirs, filenames in os.walk(treeconfig["sourcedir"]):
      if root.find('/.hg') > -1:
        continue

      newroot = root.replace(treeconfig["sourcedir"], htmlroot)

      for dir in dirs:
        newdirpath = os.path.join(newroot, dir)
        if not os.path.exists(newdirpath):
          os.makedirs(newdirpath)

      for filename in filenames:
        # Hack: Glimpse indexing needs the .cpp to exist beside the .cpp.html
        cpypath = os.path.join(newroot, filename)

        srcpath = os.path.join(root, filename)
        if debugfile is not None and not srcpath.endswith(debugfile):
          continue

        shutil.copyfile(srcpath, cpypath)
        p.apply_async(async_toHTML, [dxrconfig, treeconfig, srcpath, newroot])


    p.close()
    p.join()

    # Build glimpse index
    if not debug:
      buildglimpse = os.path.join(dxrconfig["xrefscripts"], "build-glimpseidx.sh")
      subprocess.call([buildglimpse, dxrconfig["wwwdir"], treeconfig["tree"], dbdir, dxrconfig["glimpseindex"]])

    # TODO: should I delete the .cpp, .h, .idl, etc, that were copied into wwwdir/treename-current for glimpse indexing?

def parseconfig(filename, doxref, dohtml, tree, debugfile):
    prepDone = False

    # Build the contents of an html <select> and open search links
    # for all trees encountered.
    options = ''
    opensearch = ''

    dxrconfig = dxr_config.load(filename)

    for section in dxrconfig["trees"]:
        # Look for DXR and Web and anything else is a tree description
        if section["tree"] == 'DXR' or section["tree"] == 'Web':
            continue
        else:
            # if tree is set, only index/build this section if it matches
            if tree and section["tree"] != tree:
                continue

            options += '<option value="' + section["tree"] + '">' + section["tree"] + '</option>'
            opensearch += '<link rel="search" href="opensearch-' + section["tree"] + '.xml" type="application/opensearchdescription+xml" '
            opensearch += 'title="' + section["tree"] + '" />\n'
            WriteOpenSearch(section["tree"], dxrconfig["hosturl"], dxrconfig["virtroot"], dxrconfig["wwwdir"])

            indextree(dxrconfig, section, doxref, dohtml, debugfile)

    # Generate index page with drop-down + opensearch links for all trees
    indexhtml = template.readFile(os.path.join(dxrconfig["templates"], 'dxr-index-template.html'))
    indexhtml = string.Template(indexhtml).safe_substitute(**dxrconfig)
    indexhtml = string.Template(indexhtml).safe_substitute(**section)
    indexhtml = indexhtml.replace('$OPTIONS', options)
    indexhtml = indexhtml.replace('$OPENSEARCH', opensearch)
    index = open(os.path.join(dxrconfig["wwwdir"], 'index.html'), 'w')
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
