#!/usr/bin/env python2.6

#import cgitb; cgitb.enable()
import cgi
import sqlite3
import sys
import os
import ConfigParser
import re
import subprocess

# HACK: template.py is below us
sys.path.append('./xref-scripts')
import template
import dxr_config

def like_escape(val):
  return 'LIKE "%' + val.replace("\\", "\\\\").replace("_", "\\_") \
    .replace("%", "\\%") + '%" ESCAPE "\\"'

def split_type(val):
    parts = val.split('::')
    # check for 'type' vs. 'type::member' vs. 'namespace::type::member' or 'namespace::namespace2::type::member'
    n = None
    t = None
    m = None

    if len(parts) == 1:
        # just a single string, stuff it in type
        t = val
    elif len(parts) == 2:
        t = parts[0]
        m = parts[1]
    else:
        m = parts[-1]
        t = parts[-2]
        # use the rest as namespace
        n = '::'.join(parts[0:-2])

    return n, t, m

def GetLine(loc):
    parts = loc.split(':')
    file = template.readFile(os.path.join(dxrconfig['wwwdir'], tree, parts[0]))
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

def processString(string):
  vrootfix = dxrconfig['virtroot']
  if vrootfix == '/':
    vrootfix = ''
  def printSidebarResults(name, results):
    if len(results) == 0:
      return
    print '<div class="bubble"><span class="title">%s</span><ul>' % name
    for res in results:
      # Make sure we're not matching part of the scope
      colon = res[0].rfind(':')
      if colon != -1 and res[0][colon:].find(string) == -1:
        continue
      fixloc = res[1].split(':')
      if path and not re.search(path, fixlink):
        continue
      print '<li><a href="%s/%s/%s.html#l%s">%s</a></li>' % \
        (vrootfix, tree, fixloc[0], fixloc[1], res[0])
    print '</ul></div>'

  # Print smart sidebar
  print '<div id="sidebar">'
  config = {
    'types': ['tname', 'tloc', 'tname'],
    #'macros': ['mshortname', 'mloc', 'mshortname'], XXX: need to fix table
    'variables': ['vname', 'vloc', 'vname'],
    'functions': ['flongname', 'floc', 'fname'],
  }
  for table in config:
    cols = config[table]
    results = []
    for row in conn.execute('SELECT %s FROM %s WHERE %s %s;' % (
        ', '.join(cols[:-1]), table, cols[0], like_escape(string))).fetchall():
      results.append((row[0], row[1]))
    printSidebarResults(str.capitalize(table), results)

  # Print file sidebar
  printHeader = True
  glimpsefilenames = template.readFile(os.path.join(dxrconfig['wwwdir'], tree, '.dxr_xref', '.glimpse_filenames'))
  if glimpsefilenames:
    for filename in glimpsefilenames.split('\n'):
      # Only check in leaf name
      pattern = '/([^/]*' + string + '[^/]*\.[^\.]+)$' if not ext else '/([^/]*' + string + '[^/]*\.' + ext + ')$'
      m = re.search(pattern, filename, re.IGNORECASE)
      if m:
        if printHeader:
          print '<div class=bubble><span class="title">Files</span><ul>'
          printHeader = False
        filename = filename.replace(dxrconfig['wwwdir'], vrootfix)
        print '<li><a href="%s.html">%s</a></li>' % (filename, m.group(1))
    if not printHeader:
      print "</ul></div>"

  print '</div><div id="content">'

  # Check for strings like 'foo::bar'
  halves = string.split('::')
  if len(halves) == 2:
    count = processMember(halves[1], halves[0], True)
    if count > 0:
      # we printed results, so don't bother with a text search
      return

  # Glimpse search results
  count = 0

  # ./glimpse -i -e -H ./mozilla-central/.glimpse_index/ -F 'uconv;.h$' nsString
  searchargs = '-i -y -n -H ' + os.path.join(dxrconfig['wwwdir'], tree, '.dxr_xref')
  if path:
    searchargs += " -F '" + path
    if ext:
      searchargs += ';' + ext + '$'
    searchargs += "'"
  searchargs += ' ' + string

  # TODO: should I do -L matches:files:matches/file (where 0 means infinity) ?
  # TODO: glimpse can fail in various ways, need to deal with those cases (>29 chars, no results, etc.)
  pipe = subprocess.Popen(dxrconfig['glimpse'] + ' ' + searchargs, shell=True, stdout=subprocess.PIPE).stdout
  if pipe:
    line = pipe.readline()
    prevfile = None
    first = True
    while line:
      (filepath, linenum, text) = line.split(': ', 2)
      text = cgi.escape(text)
      text = re.sub(r'(?i)(' + string + ')', '<b>\\1</b>', text)
      srcpath = filepath.replace(dxrconfig['wwwdir'] + '/', '')
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
  components = derived.split('::')
  if len(components) > 1:
    # Find out if the entire thing is a class or not
    num = conn.execute('SELECT COUNT(*) FROM types WHERE tqualname LIKE ? ' +
      'OR tqualname = ?', ('%::' + derived, derived)).fetchall()[0][0]
    if num == 0:
      base = '::'.join(components[:-1])
      func = components[-1]
    else:
      base = derived
      func = None
  else:
    base = derived
    func = None

  # Find the class in the first place
  tname, tid = conn.execute('SELECT tqualname, tid FROM types WHERE ' +
    'tqualname LIKE ? OR tqualname=?', ('%::' + base, base)).fetchall()[0]

  print '<h2>Results for %s:</h2>\n' % (cgi.escape(tname))
  # Find everyone who inherits this class
  types = conn.execute('SELECT tqualname, tid, tloc, inhtype FROM impl ' +
    'LEFT JOIN types ON (tderived = tid) WHERE tbase=? ORDER BY inhtype DESC',
    (tid,)).fetchall()

  if func is None:
    for t in types:
      direct = 'Direct' if t[3] is not None else 'Indirect'
      if not path or re.search(path, t[2]):
        print '<h3>%s (%s)</h3>' % (cgi.escape(t[0]), direct)
        print GetLine(t[2])
  else:
    typeMaps = dict([(t[1], t[0]) for t in types])
    for method in conn.execute('SELECT scopeid, flongname, floc FROM functions'+
        ' WHERE scopeid IN (' + ','.join([str(t[1]) for t in types]) + ') AND' +
        ' fname = ?', (func,)).fetchall():
      tname = cgi.escape(typeMaps[method[0]])
      mname = cgi.escape(method[1])
      if not path or re.search(path, method[2]):
        print '<h3>%s::%s</h3>' % (tname, mname)
        print GetLine(method[2])

def processMacro(macro):
    for m in conn.execute('select mname, mvalue from macros where mshortname like "' + macro + '%";').fetchall():
        mname = cgi.escape(m[0])
        mvalue = cgi.escape(m[1])
        print '<h3>%s</h3><pre>%s</pre>' % (mname, mvalue)

def processMember(member, type, printDecl):
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

        if printDecl and m[3]:
            print GetLine(m[3])
            count += 1
        if m[4]:
            print GetLine(m[4])
            count += 1
    return count

def processCallers(callers):
    n, t, m = split_type(callers)

    if not t and not m:
        return

    if n:
        # type names will include namespace
        t = n + '::' + t

    hits = conn.execute("select namespace, type, shortName from node where id in (select caller from edge where callee in (select id from node where type=? COLLATE NOCASE and shortName=? COLLATE NOCASE));", (t, m)).fetchall();
    count = 0
    for h in hits:
        count += 1
        if h[0]:
            processMember(h[2], h[0] + '::' + h[1], False)
        else:
            processMember(h[2], h[1], False)

#    # No hits on direct type, try bases
#    if count == 0:
#        hits = conn.execute("select type, shortName from node where id in (select caller from edge where callee in (select id from node where shortName=? and type in (select tbname from impl where tcname=?)));", (parts[1], parts[0])).fetchall();
#        for h in hits:
#            count += 1
#            processMember(h[1], h[0], False)

    if count == 0:
        print "No matches found.  Perhaps you want a base type?"

        # Show base types with this member
        for type in conn.execute('select tbname, tcloc, direct from impl where tcname = ? order by direct desc COLLATE NOCASE;', (t,)).fetchall():
            tname = cgi.escape(type[0])
            tdirect = 'Direct' if type[2] == 1 else 'Indirect'
            if not path or re.search(path, tloc):
                print '<h3>%s (%s)</h3>' % (tname, tdirect)
                print GetLine(type[1])

def processWarnings(warnings):
    # Check for * which means user entered "warnings:" and wants to see all of them.
    if warnings == '*':
      warnings = ''

    for w in conn.execute("select wfile, wloc, wmsg from warnings where wmsg like '%" + warnings + "%' order by wfile, wloc;").fetchall():
    	if not path or re.search(path, w[0]):
           loc = w[0] + ':' + `w[1]`
    	   print '<h3>%s</h3>' % w[2]
           print GetLine(loc)

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
callers = ''
warnings = ''

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

if form.has_key('callers'):
    callers = form['callers'].value

if form.has_key('warnings'):
    warnings = form['warnings'].value

htmldir = os.path.join('./', tree)

# TODO: kill off hard coded path
dxrconfig = dxr_config.load('./dxr.config')

#glimpse = config.get('DXR', 'glimpse')
#wwwdir = config.get('Web', 'wwwdir')
dbname = tree + '.sqlite'
dxrdb = os.path.join(dxrconfig['wwwdir'], tree, '.dxr_xref', dbname)
header_template = os.path.join(dxrconfig['templates'], 'dxr-search-header.html')
footer_template = os.path.join(dxrconfig['templates'], 'dxr-search-footer.html')
conn = sqlite3.connect(dxrdb)
conn.execute('PRAGMA temp_store = MEMORY;')

if string:
  titlestr = string
else:
  titlestr = ''
print 'Content-Type: text/html\n'
print template.expand(template.readFile(header_template), dxrconfig["virtroot"],
  tree) % (cgi.escape(titlestr), dxrconfig["virtroot"], cgi.escape(tree))

if string:
    processString(string)
else:
    print '<div id="content">'
    if type:
        if member:
            processMember(member, type, True)
        else:
            processType(type)
    elif derived:
        processDerived(derived)
    elif member:
        processMember(member, type, True)
    elif macro:
        processMacro(macro)
    elif callers:
        processCallers(callers)
    elif warnings:
    	processWarnings(warnings)

print template.readFile(footer_template)

