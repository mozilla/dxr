#!/usr/bin/env python

#import cgitb; cgitb.enable()
import cgi
import sqlite3
import sys
import os
import ConfigParser
import re
import subprocess

def GetLine(loc):
    parts = loc.split(':')
    file = ReadFile(os.path.join(wwwdir, tree, parts[0]))
    line = int(parts[1])
    if file:
        result  = '<div class="searchfile"><a href="%s/%s">%s</a></div><ul class="searchresults">' % (tree, parts[0] + '.html#l' + parts[1], loc)
        lines = file.split('\n')
        for i in [-1, 0, 1]:
            num = int(parts[1]) + i
            result += '<li class="searchresult"><a href="%s/%s">%s:</a>&nbsp;&nbsp;%s</li>' % (tree, parts[0] + '.html#l' + str(num), num, cgi.escape(lines[line+i-1]))

        result += '</ul>'
        return result
    else:
        return ''
            
def ReadFile(filename):
    """Returns the contents of a file."""
    try:
        fp = open(filename)
        try:
            return fp.read()
        finally:
            fp.close()
    except IOError:
        return None

def processString(string):
    # Print type sidebar
    printHeader = True
    printFooter = False
    print '<div id="sidebar">'
    for type in conn.execute('select tname, tloc, tkind from types where tname like "' + string + '%";').fetchall():
        tname = cgi.escape(type[0])
        tloc = type[1].replace(':', '.html#l')        
        if not path or re.search(path, tloc):
            if printHeader:
                print '<div class="bubble"><span class="title">Types</span><ul>'
                printHeader = False
                printFooter = True
            print '<li><a href="%s/%s/%s">%s</a></li>' % (virtroot, tree, tloc, tname)
    if printFooter:
        print "</ul></div>"

    # Print macro sidebar
    printHeader = True
    printFooter = False
    for type in conn.execute('select mshortname from macros where mshortname like "' + string + '%";').fetchall():
        mshortname = cgi.escape(type[0])
        if printHeader:
            print '<div class="bubble"><span class="title">Macros</span><ul>'
            printHeader = False
            printFooter = True
        print '<li><a href="%s/search.cgi?tree=%s&macro=%s">%s</a></li>' % (virtroot, tree, mshortname, mshortname)
    if printFooter:
        print "</ul></div>"

    # Print file sidebar
    printHeader = True
    printFooter = False
    glimpsefilenames = ReadFile(os.path.join(wwwdir, tree, '.dxr_xref', '.glimpse_filenames'))
    if glimpsefilenames:
        for filename in glimpsefilenames.split('\n'):
            # Only check in leaf name
            pattern = '/([^/]*' + string + '[^/]*\.[^\.]+)$' if not ext else '/([^/]*' + string + '[^/]*\.' + ext + ')$'
            m = re.search(pattern, filename, re.IGNORECASE)
            if m:
                if printHeader:
                    print '<div class=bubble><span class="title">Files</span><ul>'
                    printHeader = False
                    printFooter = True
                htmlfilename = filename.replace(wwwdir, virtroot) + '.html'
                print '<li><a href="%s">%s</a></li>' % (htmlfilename, m.group(1))
        if printFooter:
            print "</ul></div>"

    # Print member sidebar
    printHeader = True
    printFooter = False
    for m in conn.execute('select mshortname, mdef, mdecl, mtname, mname from members where mshortname like "' + string + '%";').fetchall():
        mshortname = cgi.escape(m[0])
        link = None
        if m[1]:
            link = m[1].replace(':', '.html#l')
        else:
            link = m[2].replace(':', '.html#l')

        if not path or re.search(path, link):
            if printHeader:
                print '<div class="bubble"><span class="title">Members</span><ul>'
                printHeader = False
                printFooter = True
            print '<li><a href="%s/%s" title="%s::%s">%s</a></li>' % (tree, link, m[3], m[4], mshortname)
    if printFooter:
        print "</ul></div>"

    print '</div><div id="content">'

    # Check for strings like 'foo::bar'
    halves = string.split('::')
    if len(halves) == 2:
        count = processMember(halves[1], halves[0])
        if count > 0:
            # we printed results, so don't bother with a text search
            return

    # Glimpse search results
    count = 0
    
    # ./glimpse -i -e -H ./mozilla-central/.glimpse_index/ -F 'uconv;.h$' nsString
    searchargs = '-i -y -n -H ' + os.path.join(wwwdir, tree, '.dxr_xref')
    if path:
        searchargs += " -F '" + path
        if ext:
            searchargs += ';' + ext + '$'
        searchargs += "'"
    searchargs += ' ' + string

    # TODO: should I do -L matches:files:matches/file (where 0 means infinity) ?
    # TODO: glimpse can fail in various ways, need to deal with those cases (>29 chars, no results, etc.)
    pipe = subprocess.Popen(glimpse + ' ' + searchargs, shell=True, stdout=subprocess.PIPE).stdout
    if pipe:
        line = pipe.readline()
        prevfile = None
        first = True
        while line:
            (filepath, linenum, text) = line.split(': ', 2)
            text = cgi.escape(text)
            text = re.sub(r'(?i)(' + string + ')', '<b>\\1</b>', text)
            srcpath = filepath.replace(wwwdir + '/', '')
            if filepath != prevfile:
                prevfile = filepath
                if not first:
                    print "</ul>"
                first = False
                print '<div class="searchfile"><a href="%s.html">%s</a></div><ul class="searchresults">' % (srcpath, srcpath.replace(tree + '/', ''))
            
            print '<li class="searchresult"><a href="%s.html#l%s">%s:</a>&nbsp;&nbsp;%s</li>' % (srcpath, linenum, linenum, text)
            count += 1
            line = pipe.readline()

    if count == 0:
        print '<p>No files match your search parameters.</p>'

def processType(type):
    for type in conn.execute('select tname, tloc, tkind from types where tname like "' + type + '%";').fetchall():
        tname = cgi.escape(type[0])
        if not path or re.search(path, tloc):
            print '<h3>%s (%s)</h3>' % (tname, type[2])
            print GetLine(type[1])

def processDerived(derived):
    for type in conn.execute('select tcname, tcloc, direct from impl where tbname = ? order by direct desc;', (derived,)).fetchall():
        tname = cgi.escape(type[0])
        tdirect = 'Direct' if type[2] == 1 else 'Indirect'
        if not path or re.search(path, tloc):
            print '<h3>%s (%s)</h3>' % (tname, tdirect)
            print GetLine(type[1])

def processMacro(macro):
    for m in conn.execute('select mname, mvalue from macros where mshortname like "' + macro + '%";').fetchall():
        mname = cgi.escape(m[0])
        mvalue = cgi.escape(m[1])
        print '<h3>%s</h3><pre>%s</pre>' % (mname, mvalue)

def processMember(member, type):
    members = None
    count = 0 # make sure we find something
    if type:
        members = conn.execute('select mname, mtname, mtloc, mdecl, mdef, mvalue, maccess from members where mshortname like "' + member + 
                               '%" and mtname like "' + type + '%" order by mtname, maccess, mname;').fetchall()
    else:
        members = conn.execute('select mname, mtname, mtloc, mdecl, mdef, mvalue, maccess from members where mshortname like "' + member + 
                               '%" order by mtname, maccess, mname;').fetchall()
    # TODO: is there a way to add more of the above data here?
    for m in members:
        if m[5]: # does this member have a value?
            print '<h3>%s::%s [Value = %s]</h3>' % (cgi.escape(m[1]), cgi.escape(m[0]), cgi.escape(m[5]))
        else:
            print '<h3>%s::%s</h3>' % (cgi.escape(m[1]), cgi.escape(m[0]))

        if m[3]:
            print GetLine(m[3])
            count += 1
        if m[4]:
            print GetLine(m[4])
            count += 1
    return count

# XXX: enable auto-flush on write - http://mail.python.org/pipermail/python-list/2008-June/668523.html
# reopen stdout file descriptor with write mode
# and 0 as the buffer size (unbuffered)
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

form = cgi.FieldStorage()

string = None
path = None
ext = None
type = ''
derived = ''
member = ''
tree = '' #mozilla-central' # just a default for now
macro = ''

if form.has_key('string'):
    string = form['string'].value

if form.has_key('path'):
    path = form['path'].value

if form.has_key('ext'):
    ext = form['ext'].value
    # remove . if present
    ext = ext.replace('.', '')

if form.has_key('type'):
    type = form['type'].value

if form.has_key('derived'):
    derived = form['derived'].value

if form.has_key('member'):
    member = form['member'].value

if form.has_key('tree'):
    tree = form['tree'].value

if form.has_key('macro'):
    macro = form['macro'].value

htmldir = os.path.join('./', tree)

config = ConfigParser.ConfigParser()
config.read('dxr.config')

glimpse = config.get('DXR', 'glimpse')
wwwdir = config.get('Web', 'wwwdir')
virtroot = config.get('Web', 'virtroot')
dbname = tree + '.sqlite'
dxrdb = os.path.join(wwwdir, tree, '.dxr_xref', dbname)

conn = sqlite3.connect(dxrdb)
conn.execute('PRAGMA temp_store = MEMORY;')

print """Content-Type: text/html

<!DOCTYPE HTML>
<html lang="en-US">
<head>
  <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />    
  <title>DXR Search Results - %s</title>
  <link href="dxr-search-styles.css" rel="stylesheet" type="text/css">
  <script type="text/javascript" src="%s/js/searchParser.js"></script>
  <script type="text/javascript" src="%s/js/search.js"></script>
  <script type="text/javascript">
    var virtroot = '%s';
    var tree = '%s';
  </script>
</head>
<body onload="parseQS('search-box');">
<div id="logo"><a href="%s/index.html"><img src="images/powered-by-mozilla-small.png" border="0"></a></div>
<div id="search">
  <form id="searchForm" method="post">
    <input id="search-box" name=string type=text size=31 maxlength=2048 title="Search">
    <input type=submit value="Search" onclick="return doSearch('searchForm');">
  </form>
</div>
<div id=results>
""" % (string, virtroot, virtroot, virtroot, tree, virtroot)

if string:
    processString(string)
else:
    print '<div id="content">'    
    if type:
        if member:
            processMember(member, type)
        else:
            processType(type)
    elif derived:
        processDerived(derived)
    elif member:
        processMember(member, type)
    elif macro:
        processMacro(macro)

print """</div></div></body></html>"""
