#!/usr/bin/env python

import os, sys, getopt, ConfigParser, subprocess

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

def parseconfig(filename, doxref, dohtml, tree):
    prepDone = False
    config = ConfigParser.ConfigParser()
    config.read(filename)

    xrefscripts = None
    wwwsrcfiles = None
    wwwdir = None
    virtroot = None

    # Build the contents of an html <select> for all trees encountered
    options = ''

    xrefscripts = config.get('DXR', 'xrefscripts')
    wwwsrcfiles = config.get('DXR', 'wwwsrcfiles')
    wwwdir = config.get('Web', 'wwwdir')
    virtroot = config.get('Web', 'virtroot')

    for section in config.sections():
        # Look for DXR and Web and anything else is a tree description
        if section == 'DXR' or section == 'Web':
            continue
        else:
            # if tree is set, only index/build this section if it matches
            if tree and section != tree:
                continue
            options += '<option value="' + section + '">' + section + '</option>'
            sourcedir = config.get(section, 'sourcedir')
            objdir = config.get(section, 'objdir')
            mozconfig = config.get(section, 'mozconfig')

            # dxr xref files (glimpse + sqlitedb) go in wwwdir/treename-current/.dxr_xref
            # and we'll symlink it to wwwdir/treename later
            dbdir = os.path.join(wwwdir, section + '-current', '.dxr_xref')
            dbname = section + '.sqlite'

            retcode = 0
            # Build dxr.sqlite
            if doxref:
                buildxref = os.path.join(xrefscripts, "build-xref.sh")
                retcode = subprocess.call([buildxref, sourcedir, objdir, mozconfig, xrefscripts, dbdir, dbname, wwwdir, section])
                if retcode != 0:
                    sys.exit(retcode)

            # Build static html
            if dohtml:
                buildhtml = os.path.join(xrefscripts, "build-html.sh")
                htmlheader = os.path.join(wwwsrcfiles, "dxr-header.html")
                htmlfooter = os.path.join(wwwsrcfiles, "dxr-footer.html")
                dxrsqlite = os.path.join(dbdir, dbname)
                
                retcode = subprocess.call([buildhtml, wwwdir, sourcedir, htmlheader, htmlfooter, dxrsqlite, section, virtroot])
                if retcode != 0:
                    sys.ext(retcode)

                # Build glimpse index
                buildglimpse = os.path.join(xrefscripts, "build-glimpseidx.sh")
                glimpseindex = config.get('DXR', 'glimpseindex')
                retcode = subprocess.call([buildglimpse, wwwdir, section, dbdir, glimpseindex])

    # Generate index page with drop-down for all trees
    indexhtml = ReadFile(os.path.join(wwwsrcfiles, 'dxr-index-template.html'))
    indexhtml = indexhtml.replace('$OPTIONS', options)
    index = open(os.path.join(wwwdir, 'index.html'), 'w')
    index.write(indexhtml)
    index.close()

    # TODO: need proper exit handling so you can C-c and kill subprocesses spawned in the bash scripts


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
