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
try:
  config.read(['/etc/dxr/dxr.config', './dxr.config'])
  sys.path.append(config.get('DXR', 'dxrroot'))
except:
  msg = sys.exc_info()[1] # Python 2/3 compatibility
  print 'Content-Type: text/html\n'
  print '<body><h3>Error: Failed to open either %s/dxr.config ' \
        'or /etc/dxr/dxr.config</h3><p>%s</body>' % (os.getcwd(), msg)
  sys.exit (0)
import dxr
import dxr.stopwatch

watch = dxr.stopwatch.StopWatch()

def print_timing(watch):
  total = watch.elapsed('total')
  query = watch.elapsed('query')
  formatting = watch.elapsed('formatting')
  sidebar = watch.elapsed('sidebar')

  remaining = total - (query + formatting + sidebar)

  if total > 0:
    print """<small>
It took %.3fs to generate this content (Query: %.2f%%,
Formatting: %.2f%%, Sidebar contents: %.2f%%, Uncharted: %.2f%%)
</small>""" % (total,
               ((query * 100) / total),
               ((formatting * 100) / total),
               ((sidebar * 100) / total),
               ((remaining * 100) / total))

def print_user_timing():
  print """<br/><small>Total request time (as seen by the user):
  <script type="text/javascript">
    printRequestTime();
  </script>
</small>"""

def like_escape(val):
  return 'LIKE "%' + val.replace("\\", "\\\\").replace("_", "\\_") \
    .replace("%", "\\%") + '%" ESCAPE "\\"'

def GetLine(loc):
  # Load the parts
  parts = loc.split(':')
  fname, line = parts[0], int(parts[1])

  output = ('<div class="searchfile"><a href="%s/%s.html#l%d">' +
            '%s</a></div><ul class="searchresults">\n') % (tree, fname, line, loc)

  text = conn.execute('SELECT fts.content FROM fts where fts.rowid = (select ID from files where path = \'%s\')' % fname).fetchone()[0]
  text_start = 0

  # Show [line - 1, line, line + 1] unless we see more
  for i in xrange (line - 1):
    text_start = text.find ("\n", text_start) + 1

  for i in xrange (3):
    text_end = text.find ("\n", text_start);

    output += ('<li class="searchresult"><a href="%s/%s.html#l%s">%s:</a>' +
               '&nbsp;&nbsp;%s</li>\n') % (tree, fname,
                                           line + i,
                                           line + i,
                                           cgi.escape(text[text_start:text_end]))
    text_start = text_end + 1

  output += '</ul>'
  return output

def regexp(expr, item):
  reg = re.compile(expr)
  try:
    return reg.search(item) is not None
  except:
    return False

def processString(string, path=None, ext=None, regexp=None):
  global watch

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

  watch.start('sidebar')

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

  for row in conn.execute('SELECT (SELECT path from files where ID = fts.rowid), fts.basename ' +
                          'FROM fts where fts.basename MATCH \'%s\'' % string).fetchall():
    if printHeader:
      print '<div class=bubble><span class="title">Files</span><ul>'
      printHeader = False
    filename = vrootfix + '/' + tree + '/' + row[0]
    print '<li><a href="%s.html">%s</a></li>' % (filename, row[1])

  if not printHeader:
    print "</ul></div>"

  watch.stop('sidebar')
  print '</div><div id="content">'

  # Text search results
  first = True
  watch.start('query')

  if regexp is None:
    for row in conn.execute('SELECT (SELECT path from files where ID = fts.rowid), ' +
                            ' fts.content, offsets(fts) FROM fts where fts.content ' +
                            'MATCH \'%s\'' % (string)).fetchall():
      if first:
        # The first iteration in the resultset fetches all the values
        watch.stop('query')

      first = False
      print '<div class="searchfile"><a href="%s/%s/%s.html">%s</a></div><ul class="searchresults">' % (vrootfix, tree, row[0], row[0])

      watch.start('formatting')
      line_count = 0
      last_pos = 0

      content = row[1]
      offsets = row[2].split();
      offsets = [offsets[i:i+4] for i in xrange(0, len(offsets), 4)]

      for off in offsets:
        line_count += content.count ("\n", last_pos, int (off[2]))
        last_pos = int (off[2])

        line_str = content [content.rfind ("\n", 0, int (off[2]) + 1) :
                            content.find ("\n", int (off[2]))]

        line_str = cgi.escape(line_str)
        line_str = re.sub(r'(?i)(' + string + ')', '<b>\\1</b>', line_str)

        print '<li class="searchresult"><a href="%s/%s/%s.html#l%s">%s:</a>&nbsp;&nbsp;%s</li>' % (vrootfix, tree, row[0], line_count + 1, line_count + 1, line_str)

      watch.stop('formatting')
      print '</ul>'

  else:
    for row in conn.execute('SELECT (SELECT path from files where ID = fts.rowid),' +
                            'fts.content FROM fts where fts.content REGEXP (\'%s\')' % (string)).fetchall():
      if first:
        # The first iteration in the resultset fetches all the values
        watch.stop('query')

      first = False
      print '<div class="searchfile"><a href="%s/%s/%s.html">%s</a></div><ul class="searchresults">' % (vrootfix, tree, row[0], row[0])

      watch.start('formatting')
      line_count = 0
      last_pos = 0
      content = row[1]

      for m in re.finditer (string, row[1]):
        offset = m.start ()

        line_count += content.count ("\n", last_pos, offset)
        last_pos = offset

        line_str = content [content.rfind ("\n", 0, offset + 1) :
                            content.find ("\n", offset)]

        line_str = cgi.escape(line_str)
        line_str = re.sub(r'(?i)(' + string + ')', '<b>\\1</b>', line_str)

        print '<li class="searchresult"><a href="%s/%s/%s.html#l%s">%s:</a>&nbsp;&nbsp;%s</li>' % (vrootfix, tree, row[0], line_count + 1, line_count + 1, line_str)

      watch.stop('formatting')
      print '</ul>'

  if first:
    print '<p>No files match your search parameters.</p>'

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

print 'Content-Type: text/html\n'

# Load the configuration files
try:
  dxrconfig = dxr.load_config()
except:
  msg = sys.exc_info()[1] # Python 2/3 compatibility
  print '<body><h3>Error: Failed to parse dxr.config ' \
        'or /etc/dxr/dxr.config</h3><p>%s</body>' % (os.getcwd(), msg)
  sys.exit (0)

tree = 'undefined'
for treecfg in dxrconfig.trees:
  if 'tree' in form and treecfg.tree != form['tree']:
    continue
  dxrconfig = treecfg
  tree = treecfg.tree
  break

if tree == 'undefined':
  print dxrconfig.getTemplateFile("dxr-search-header.html") % 'Error'
  print '<h3>Error: Specified tree %s is invalid</h3>' % \
    ('tree' in form and form['tree'] or tree)
  sys.exit (0)

try:
  # Load the database
  dbname = tree + '.sqlite'
  dxrdb = os.path.join(treecfg.dbdir, dbname)
  conn = sqlite3.connect(dxrdb)
  conn.text_factory = str
  conn.create_function ('REGEXP', 2, regexp)
  conn.execute('PRAGMA temp_store = MEMORY;')
except:
  msg = sys.exc_info()[1] # Python 2/3 compatibility
  print dxrconfig.getTemplateFile("dxr-search-header.html") % 'Error'
  print '<h3>Error: Failed to open %s</h3><p>%s' % (filename, msg)
  sys.exit (0)

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
  ('string', processString, True, '%s', ['path', 'ext', 'regexp'])
]

watch.start('total')

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

watch.stop('total')
print_timing(watch)

if 'request_time' in form:
  print_user_timing()

print dxrconfig.getTemplateFile("dxr-search-footer.html")
