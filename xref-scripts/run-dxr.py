#!/usr/bin/env python

try:
    # python 2.6
    from multiprocessing import Pool, cpuCount
except ImportError:
    try:
        # pyprocessing - http://developer.berlios.de/projects/pyprocessing
        from processing import Pool, cpuCount
    except ImportError:
        print >>sys.stderr, "No processing library available! Install pyprocessing or Python 2.6"
        sys.exit(1)

import os, sys, getopt, ConfigParser, subprocess
import idl2html, cpp2html
import shutil

def usage():
    print """Usage: run-dxr.py [options]
Options:
  -h, --help                              Show help information.
  -f, --file    FILE                      Use FILE as config file (default is ./dxr.config).
  -t, --tree    TREE                      Indxe and Build only section TREE (default is all).
  -c, --create  [xref|html]               Create xref or html and glimpse index (default is all)."""

def ReadFile(filename, print_error=True):
    """Returns the contents of a file."""
    try:
        fp = open(filename)
        try:
            return fp.read()
        finally:
            fp.close()
    except IOError:
        if print_error:
            print('Error reading %s: %s' % (filename, sys.exc_info()[1]))
            return None

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

def indextree(tree, sourcedir, objdir, mozconfig, wwwdir, xrefscripts, templatesdir, virtroot, glimpseindex, doxref, dohtml):
    # dxr xref files (glimpse + sqlitedb) go in wwwdir/treename-current/.dxr_xref
    # and we'll symlink it to wwwdir/treename later
    htmlroot = os.path.join(wwwdir, tree + '-current')
    dbdir = os.path.join(htmlroot, '.dxr_xref')
    dbname = tree + '.sqlite'

    retcode = 0
    # Build dxr.sqlite
    if doxref:
        buildxref = os.path.join(xrefscripts, "build-xref.sh")
        retcode = subprocess.call([buildxref, sourcedir, objdir, mozconfig, xrefscripts, dbdir, dbname, wwwdir, tree])
        if retcode != 0:
            return

    # Build static html
    if dohtml:
        buildhtml = os.path.join(xrefscripts, "build-html.sh")
        htmlheader = ReadFile(os.path.join(templatesdir, "dxr-header.html"))
        htmlfooter = ReadFile(os.path.join(templatesdir, "dxr-footer.html"))
        dxrsqlite = os.path.join(dbdir, dbname)
                
        n = cpuCount()
        p = Pool(processes=n)

        print 'Building HTML files for ' + tree +  '...'

        for root, dirs, filenames in os.walk(sourcedir):
            if root.find('/.hg') > -1:
                continue

            newroot = root.replace(sourcedir, htmlroot)
            
            for dir in dirs:
                newdirpath = os.path.join(newroot, dir)
                if not os.path.exists(newdirpath):
                    os.makedirs(newdirpath)
                    
            for filename in filenames:
                srcpath = os.path.join(root, filename)
                # Hack: Glimpse indexing needs the .cpp to exist beside the .cpp.html
                cpypath = os.path.join(newroot, filename)
                if filename.endswith('.cpp') or filename.endswith('.h'):
                    shutil.copyfile(srcpath, cpypath)
                    p.apply_async(cpp2htmlparallel.FormatSource, (htmlheader, htmlfooter, dxrsqlite, sourcedir, virtroot, tree, srcpath, newroot))
                elif filename.endswith('.idl'):
                    shutil.copyfile(srcpath, cpypath)
                    p.apply_async(idl2htmlparallel.FormatSource, (htmlheader, htmlfooter, dxrsqlite, sourcedir, virtroot, tree, srcpath, newroot))

        p.close()
        p.join()

        # Build glimpse index
        buildglimpse = os.path.join(xrefscripts, "build-glimpseidx.sh")
        subprocess.call([buildglimpse, wwwdir, tree, dbdir, glimpseindex])

        # TODO: should I delete the .cpp, .h, .idl, etc, that were copied into wwwdir/treename-current for glimpse indexing?

def parseconfig(filename, doxref, dohtml, tree):
    prepDone = False
    config = ConfigParser.ConfigParser()
    config.read(filename)

    xrefscripts = None
    templates = None
    wwwdir = None
    virtroot = None
    hosturl = None

    # Build the contents of an html <select> and open search links
    # for all trees encountered.
    options = ''
    opensearch = ''

    # Strip any trailing slashes from path strings
    xrefscripts = config.get('DXR', 'xrefscripts')
    if xrefscripts.endswith('/'):
        xrefscripts = xrefscripts[0:-1]

    templates = config.get('DXR', 'templates')
    if templates.endswith('/'):
        templates = templates[0:-1]

    wwwdir = config.get('Web', 'wwwdir')
    if wwwdir.endswith('/'):
        wwwdir = wwwdir[0:-1]

    virtroot = config.get('Web', 'virtroot')
    if virtroot.endswith('/'):
        virtroot = virtroot[0:-1]

    hosturl = config.get('Web', 'hosturl')
    if hosturl.endswith('/'):
        hosturl = hosturl[0:-1]

    glimpseindex = config.get('DXR', 'glimpseindex')

    p = Pool(processes=2)

    for section in config.sections():
        # Look for DXR and Web and anything else is a tree description
        if section == 'DXR' or section == 'Web':
            continue
        else:
            # if tree is set, only index/build this section if it matches
            if tree and section != tree:
                continue
            options += '<option value="' + section + '">' + section + '</option>'
            opensearch += '<link rel="search" href="opensearch-' + section + '.xml" type="application/opensearchdescription+xml" '
            opensearch += 'title="' + section + '" />\n'

            WriteOpenSearch(section, hosturl, virtroot, wwwdir)
            sourcedir = config.get(section, 'sourcedir')
            if sourcedir.endswith('/'):
                sourcedir = sourcedir[0:-1]
            objdir = config.get(section, 'objdir')
            if objdir.endswith('/'):
                objdir = objdir[0:-1]
            mozconfig = config.get(section, 'mozconfig')

            p.apply_async(indextree, (section, sourcedir, objdir, mozconfig, wwwdir, xrefscripts, templates, virtroot, glimpseindex, doxref, dohtml))

    p.close()
    p.join()

    # Generate index page with drop-down + opensearch links for all trees
    indexhtml = ReadFile(os.path.join(templates, 'dxr-index-template.html'))
    indexhtml = indexhtml.replace('$OPTIONS', options)
    indexhtml = indexhtml.replace('$OPENSEARCH', opensearch)
    index = open(os.path.join(wwwdir, 'index.html'), 'w')
    index.write(indexhtml)
    index.close()


if __name__ == '__main__':
    def main(argv):
        configfile = './dxr.config'
        doxref = True
        dohtml = True
        doglimpse = True
        tree = None

        try:
            opts, args = getopt.getopt(argv, "hc:f:t:", ["help", "create=", "file=", "tree="])                               
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

        parseconfig(configfile, doxref, dohtml, tree)

    main(sys.argv[1:])
