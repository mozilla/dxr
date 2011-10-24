#!/usr/bin/env python2

import cgitb; cgitb.enable()
import cgi
import sqlite3
import sys
import os
import ConfigParser
import re

# Get the DXR installation point from dxr.config
config = ConfigParser.ConfigParser()
config.read('dxr.config')
sys.path.append(config.get('DXR', 'dxrroot'))
import dxr

def like_escape(val):
  return 'LIKE "%' + val.replace("\\", "\\\\").replace("_", "\\_") \
    .replace("%", "\\%") + '%" ESCAPE "\\"'

def GetLine(loc):
  # Load the parts
  parts = loc.split(':')
  fname, line = parts[0], int(parts[1])
  if fname not in offset_cache:
    return '<p>Error: Cannot find file %s</p>' % fname

  # Open up the master file
  master_text.seek(offset_cache[fname])

  output = ('<div class="searchfile"><a href="%s/%s.html#l%d">' +
    '%s</a></div><ul class="searchresults">\n') % (tree, fname, line, loc)
  # Show [line - 1, line, line + 1] unless we see more
  read = [line - 1, line, line + 1]
  while True:
    readname, readline, readtext = master_text.readline().split(':', 2)
    line_num = int(readline)
    if readname != fname or line_num > read[-1]:
      break
    if line_num not in read:
      continue
    output += ('<li class="searchresult"><a href="%s/%s.html#l%s">%s:</a>' +
      '&nbsp;&nbsp;%s</li>\n') % (tree, fname, readline, readline,
      cgi.escape(readtext))
  output += '</ul>'
  return output

def processString(string, path=None, ext=None):
  vrootfix = dxrconfig.virtroot
  if vrootfix == '/':
    vrootfix = ''
  if ext is not None and ext[0] == '.':
    ext = ext[1:]
  def printSidebarResults(name, results):
    outputtedResults = False
    for res in results:
      # Make sure we're not matching part of the scope
      colon = res[0].rfind(':')
      if colon != -1 and res[0][colon:].find(string) == -1:
        continue
      fixloc = res[1].split(':')
      if path and not re.search(path, fixloc[0]):
        continue
      if not outputtedResults:
        outputtedResults = True
        print '<div class="bubble"><span class="title">%s</span><ul>' % name
      print '<li><a href="%s/%s/%s.html#l%s">%s</a></li>' % \
        (vrootfix, tree, fixloc[0], fixloc[1], res[0])
    if outputtedResults:
      print '</ul></div>'

  # Print smart sidebar
  print '<div id="sidebar">'
  config = [
    ('types', ['tname', 'tloc', 'tname']),
    ('macros', ['macroname', 'macroloc', 'macroname']),
    ('functions', ['fqualname', 'floc', 'fname']),
    ('variables', ['vname', 'vloc', 'vname']),
  ]
  for table, cols in config:
    results = []
    for row in conn.execute('SELECT %s FROM %s WHERE %s %s;' % (
        ', '.join(cols[:-1]), table, cols[0], like_escape(string))).fetchall():
      results.append((row[0], row[1]))
    printSidebarResults(str.capitalize(table), results)

  # Print file sidebar
  printHeader = True
  filenames = dxr.readFile(os.path.join(treecfg.dbdir, 'file_list.txt'))
  if filenames:
    for filename in filenames.split('\n'):
      # Only check in leaf name
      pattern = '/([^/]*' + string + '[^/]*\.[^\.]+)$' if not ext else '/([^/]*' + string + '[^/]*\.' + ext + ')$'
      m = re.search(pattern, filename, re.IGNORECASE)
      if m:
        if printHeader:
          print '<div class=bubble><span class="title">Files</span><ul>'
          printHeader = False
        filename = vrootfix + '/' + tree + '/' + filename
        print '<li><a href="%s.html">%s</a></li>' % (filename, m.group(1))
    if not printHeader:
      print "</ul></div>"

  print '</div><div id="content">'

  # Text search results
  prevfile, first = None, True
  master_text.seek(0)
  for line in master_text:
    # The index file is <path>:<line>:<text>
    colon = line.find(':')
    colon2 = line.find(':', colon)
    if path and line.find(path, 0, colon) == -1: continue # Not our file
    if line.find(string, colon2 + 1) != -1:
      # We have a match!
      (filepath, linenum, text) = line.split(':', 2)
      text = cgi.escape(text)
      text = re.sub(r'(?i)(' + string + ')', '<b>\\1</b>', text)
      if filepath != prevfile:
        prevfile = filepath
        if not first:
          print "</ul>"
        first = False
        print '<div class="searchfile"><a href="%s/%s/%s.html">%s</a></div><ul class="searchresults">' % (vrootfix, tree, filepath, filepath)

      print '<li class="searchresult"><a href="%s/%s/%s.html#l%s">%s:</a>&nbsp;&nbsp;%s</li>' % (vrootfix, tree, filepath, linenum, linenum, text)

  if first:
    print '<p>No files match your search parameters.</p>'
  else:
    print '</ul>'

def processType(type, path=None):
  for type in conn.execute('select * from types where tname like "' + type + '%";').fetchall():
    tname = cgi.escape(type['tname'])
    if not path or re.search(path, type['tloc']):
      info = type['tkind']
      if info == 'typedef':
        typedef = conn.execute('SELECT ttypedef FROM typedefs WHERE tid=?',
            (type['tid'],)).fetchone()[0]
        info += ' ' + cgi.escape(typedef)
      print '<h3>%s (%s)</h3>' % (tname, info)
      print GetLine(type['tloc'])

def processDerived(derived, path=None):
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
    for method in conn.execute('SELECT scopeid, fqualname, floc FROM functions'+
        ' WHERE scopeid IN (' + ','.join([str(t[1]) for t in types]) + ') AND' +
        ' fname = ?', (func,)).fetchall():
      tname = cgi.escape(typeMaps[method[0]])
      mname = cgi.escape(method[1])
      if not path or re.search(path, method[2]):
        print '<h3>%s::%s</h3>' % (tname, mname)
        print GetLine(method[2])

def processMacro(macro):
  for m in conn.execute('SELECT * FROM macros WHERE macroname LIKE "' +
      macro + '%";').fetchall():
    mname = m['macroname']
    if m['macroargs']:
      mname += m['macroargs']
    mtext = m['macrotext'] and m['macrotext'] or ''
    print '<h3>%s</h3><pre>%s</pre>' % (cgi.escape(mname), cgi.escape(mtext))
    print GetLine(m['macroloc'])

def processFunction(func):
  for f in conn.execute('SELECT * FROM functions WHERE fqualname LIKE "%' +
      func + '%";').fetchall():
    print '<h3>%s</h3>' % cgi.escape(f['fqualname'])
    print GetLine(f['floc'])

def processVariable(var):
  for v in conn.execute('SELECT * FROM variables WHERE vname LIKE "%' +
      var + '%";').fetchall():
    qual = v['modifiers'] and v['modifiers'] or ''
    print '<h3>%s %s %s</h3>' % (cgi.escape(qual), cgi.escape(v['vtype']),
      cgi.escape(v['vname']))
    print GetLine(v['vloc'])

def processWarnings(warnings, path=None):
  # Check for * which means user entered "warnings:" and wants to see all of them.
  if warnings == '*':
    warnings = ''

  num_warnings = 0
  for w in conn.execute("SELECT wloc, wmsg FROM warnings WHERE wmsg LIKE '%" +
      warnings + "%' ORDER BY wloc COLLATE loc;").fetchall():
    if not path or re.search(path, w[0]):
      print '<h3>%s</h3>' % w[1]
      print GetLine(w[0])
      num_warnings += 1
  if num_warnings == 0:
    print '<h3>No warnings found.</h3>'

def processCallers(caller, path=None, funcid=None):
  # I could handle this with a single call, but that gets a bit complicated.
  # Instead, let's first find the function that we're trying to find.
  cur = conn.cursor()
  if funcid is None:
    cur.execute('SELECT * FROM functions WHERE fqualname %s' %
      like_escape(caller))
    funcinfos = cur.fetchall()
    if len(funcinfos) == 0:
      print '<h2>No results found</h2>'
      return
    elif len(funcinfos) > 1:
      print '<h3>Ambiguous function:</h3><ul>'
      for funcinfo in funcinfos:
        print ('<li><a href="search.cgi?callers=%s&funcid=%d&tree=%s">%s</a>' +
          ' at %s</li>') % (caller, funcinfo['funcid'], tree,
          funcinfo['fqualname'], funcinfo['floc'])
      print '</ul>'
      return
    funcid = funcinfos[0]['funcid']
  # We have two cases: direct calls or we're in targets
  cur = conn.cursor()
  for info in cur.execute("SELECT functions.* FROM functions " +
      "LEFT JOIN callers ON (callers.callerid = funcid) WHERE targetid=? " +
      "UNION SELECT functions.* FROM functions LEFT JOIN callers " +
      "ON (callers.callerid = functions.funcid) LEFT JOIN targets USING " +
      "(targetid) WHERE targets.funcid=?", (funcid, funcid)):
    if not path or re.search(path, info['floc']):
      print '<h3>%s</h3>' % info['fqualname']
      print GetLine(info['floc'])
  if cur.rowcount == 0:
    print '<h3>No results found</h3>'

# XXX: enable auto-flush on write - http://mail.python.org/pipermail/python-list/2008-June/668523.html
# reopen stdout file descriptor with write mode
# and 0 as the buffer size (unbuffered)
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

# Load query parameters
fieldStorage = cgi.FieldStorage()
form = dict((key, fieldStorage.getvalue(key)) for key in fieldStorage.keys())

# Which tree are we searching
if 'tree' in form:
  tree = form['tree']
else:
  # XXX: all trees? default trees? What to do?
  tree = ''

# XXX: We're assuming dxr.config is in the same place as the web directory.
# May want to assume standard system location or something for easier large
# deployments

# Load the configuration files
dxrconfig = dxr.load_config('./dxr.config')
for treecfg in dxrconfig.trees:
  if treecfg.tree == tree:
    dxrconfig = treecfg
    break
else:
  # XXX: no tree, we're defaulting to the last one
  dxrconfig = treecfg

# Load the database
dbname = tree + '.sqlite'
dxrdb = os.path.join(treecfg.dbdir, dbname)
conn = sqlite3.connect(dxrdb)
conn.execute('PRAGMA temp_store = MEMORY;')

print 'Content-Type: text/html\n'

# Master text index, load it
try:
  master_text = open(os.path.join(treecfg.dbdir, 'file_index.txt'), 'r')
  f = open(os.path.join(treecfg.dbdir, 'index_index.txt'), 'r')
except:
  print dxrconfig.getTemplateFile("dxr-search-header.html") % 'Error'
  print '<h3>Error: file_index.txt or index_index.txt not found</h3>'
  sys.exit (0)
offset_cache = {}
try:
  for line in f:
    l = line.split(':')
    offset_cache[l[0]] = int(l[-1])
finally:
  f.close()

# This makes results a lot more fun!
def collate_loc(str1, str2):
  parts1 = str1.split(':')
  parts2 = str2.split(':')
  for i in range(1, len(parts1)):
    parts1[i] = int(parts1[i])
  for i in range(2, len(parts2)):
    parts2[i] = int(parts2[i])
  return cmp(parts1, parts2)
conn.create_collation("loc", collate_loc)
conn.row_factory = sqlite3.Row

# Output the text results.


# XXX... plugins!
searches = [
  ('type', processType, False, 'Types %s', ['path']),
  ('function', processFunction, False, 'Functions %s', []),
  ('variable', processVariable, False, 'Functions %s', []),
  ('derived', processDerived, False, 'Derived from %s', ['path']),
  ('macro', processMacro, False, 'Macros %s', []),
  ('warnings', processWarnings, False, 'Warnings %s', ['path']),
  ('callers', processCallers, False, 'Callers of %s', ['path', 'funcid']),
  ('string', processString, True, '%s', ['path', 'ext'])
]
for param, dispatch, hasSidebar, titlestr, optargs in searches:
  if param in form:
    titlestr = cgi.escape(titlestr % form[param])
    print dxrconfig.getTemplateFile("dxr-search-header.html") % titlestr
    if not hasSidebar:
      print '<div id="content">'
    kwargs = dict((k,form[k]) for k in optargs if k in form)
    dispatch(form[param], **kwargs)
    break
else:
  print dxrconfig.getTemplateFile("dxr-search-header.html") % 'Error'
  print '<h3>Error: unknown search parameters</h3>'

master_text.close()
print dxrconfig.getTemplateFile("dxr-search-footer.html")

