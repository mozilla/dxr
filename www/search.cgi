#!/usr/bin/env python

import cgitb; cgitb.enable()
import ctypes
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
from dxr import queries

try:
  ctypes_init_tokenizer = ctypes.CDLL(config.get('DXR', 'dxrroot') + "/sqlite/libdxr-code-tokenizer.so").dxr_code_tokenizer_init
  ctypes_init_tokenizer ()
except:
  msg = sys.exc_info()[1] # Python 2/3 compatibility
  print "Could not load tokenizer: %s" % msg
  sys.exit (0)

watch = dxr.stopwatch.StopWatch()

def redirect_to(str, path, line=None):
  url = '%s/%s/%s.html' % (dxrconfig.virtroot, tree, path)
  url += '?string=' + cgi.escape(str)

  if line is not None:
    url += '#l%d' % (line,)

  print '<html><head><meta http-equiv="REFRESH" content="0;url=%s"></head></html>' % (url,)

def maybe_redirect(string):
  # we only match on 1 term
  if ' ' in string:
    return False

  # match for filenames
  row = conn.execute("SELECT path FROM files where path like ?", ("%%/%s" % (string,),)).fetchall()

  if row is not None and len(row) == 1:
    redirect_to(string, row[0][0]);
    return True

  #match for type names
  row = conn.execute("SELECT (SELECT path FROM files WHERE files.ID=types.file_id), " +
                     "file_line FROM types where tname=?", (string,)).fetchall()

  if row is not None and len(row) == 1:
    redirect_to(string, row[0][0], row[0][1])
    return True

  #match for function fqnames
  row = conn.execute("SELECT (SELECT path FROM files WHERE files.ID=functions.file_id), " +
                     "file_line FROM functions where fname=?", (string,)).fetchall()

  if row is not None and len(row) == 1:
    redirect_to(string, row[0][0], row[0][1])
    return True

  return False

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

def GetLine(rowid, line, col):
  row = conn.execute('SELECT fts.content, (SELECT path FROM files where files.ID = fts.rowid) FROM fts where fts.rowid = ?', (rowid,)).fetchone()

  if row is None:
    return ''

  text = row[0]
  fname = row[1]
  text_start = 0

  output = ('<div class="searchfile"><a href="%s/%s.html#l%d">' +
            '%s:%d:%d</a></div><ul class="searchresults">\n') % (tree, fname, line, fname, line, col)

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
      if colon != -1 and res[0].lower()[colon:].find(string.lower()) == -1:
        continue
      if path and path.lower() != res[1].lower():
        continue
      if not outputtedResults:
        outputtedResults = True
        print '<div class="bubble"><span class="title">%s</span><ul>' % name
      print '<li><a href="%s/%s/%s.html#l%d">%s</a></li>' % \
        (vrootfix, tree, res[1], res[2], res[0])
    if outputtedResults:
      print '</ul></div>'

  watch.start('sidebar')

  # Print smart sidebar
  print '<div id="sidebar">'
  config = [
    ('types', ['tname']),
    ('macros', ['macroname']),
    ('functions', ['fqualname', 'fname']),
    ('variables', ['vname']),
  ]
  for table, cols in config:
    results = []
    if len(cols) > 1:
      search_col = cols[1]
    else:
      search_col = cols[0]

    for row in conn.execute('SELECT %s , (SELECT path FROM files WHERE files.ID = %s.file_id), file_line, file_col FROM %s WHERE %s %s;' % (
        cols[0], table, table, search_col, like_escape(string))).fetchall():
      results.append((row[0], row[1], row[2], row[3]))
    printSidebarResults(str.capitalize(table), results)

  # Print file sidebar
  printHeader = True

  for row in queries.getFileMatches(conn, string):
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
  prevpath = None
  watch.start('query')

  if regexp is None:
    matches = queries.getFTSMatches(conn, string)
  else:
    matches = queries.getRegexMatches(conn, string)

  for row in matches:
    if first:
      # The first iteration in the resultset fetches all the values
      watch.stop('query')
      watch.start('formatting')
      first = False

    if prevpath is None or prevpath != row[0]:
      if prevpath is not None:
        print '</ul>'
      print '<div class="searchfile"><a href="%s/%s/%s.html">%s</a></div><ul class="searchresults">' % (vrootfix, tree, row[0], row[0])

    line_str = cgi.escape(row[2])
    line_str = re.sub(r'(?i)(' + string + ')', '<b>\\1</b>', line_str)

    print '<li class="searchresult"><a href="%s/%s/%s.html#l%s">%s:</a>&nbsp;&nbsp;%s</li>' % (vrootfix, tree, row[0], row[1] + 1, row[1] + 1, line_str)
    prevpath = row[0]

  watch.stop('formatting')

  if first is True:
    print '<p>No files match your search parameters.</p>'
  else:
    print '</ul>'

def processType(type, path=None):
  for type in conn.execute('select *, (SELECT path FROM files WHERE files.ID=types.file_id) AS file_path from types where tname like "' + type + '%";').fetchall():
    tname = cgi.escape(type['tname'])
    if not path or re.search(path, type['file_path']):
      info = type['tkind']
      if info == 'typedef':
        typedef = conn.execute('SELECT ttypedef FROM typedefs WHERE tid=?',
            (type['tid'],)).fetchone()[0]
        info += ' ' + cgi.escape(typedef)
      print '<h3>%s (%s)</h3>' % (tname, info)
      print GetLine(type['file_id'], type['file_line'], type['file_col'])

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
  types = conn.execute('SELECT tqualname, tid, inhtype, file_id, file_line, file_col,' +
    '(SELECT path FROM files WHERE files.ID=types.file_id) AS file_path ' +
    'FROM impl ' +
    'LEFT JOIN types ON (tderived = tid) WHERE tbase=? ORDER BY inhtype DESC',
    (tid,)).fetchall()

  if func is None:
    for t in types:
      direct = 'Direct' if t[2] is not None else 'Indirect'
      if not path or re.search(path, t[6]):
        print '<h3>%s (%s)</h3>' % (cgi.escape(t[0]), direct)
        print GetLine(t[3], t[4], t[5])
  else:
    typeMaps = dict([(t[1], t[0]) for t in types])
    for method in conn.execute('SELECT scopeid, fqualname, file_id, file_line, file_col,' +
        ' (SELECT path FROM files WHERE files.ID=functions.file_id) AS file_path ' +
        ' FROM functions'+
        ' WHERE scopeid IN (' + ','.join([str(t[1]) for t in types]) + ') AND' +
        ' fname = ?', (func,)).fetchall():
      tname = cgi.escape(typeMaps[method[0]])
      mname = cgi.escape(method[1])
      if not path or re.search(path, method[5]):
        print '<h3>%s::%s</h3>' % (tname, mname)
        print GetLine(method[2], method[3], method[4])

def processMacro(macro):
  for m in conn.execute('SELECT * FROM macros WHERE macroname LIKE "' +
      macro + '%";').fetchall():
    mname = m['macroname']
    if m['macroargs']:
      mname += m['macroargs']
    mtext = m['macrotext'] and m['macrotext'] or ''
    print '<h3>%s</h3><pre>%s</pre>' % (cgi.escape(mname), cgi.escape(mtext))
    print GetLine(m['file_id'], m['file_line'], m['file_col'])

def processFunction(func):
  for f in conn.execute('SELECT * FROM functions WHERE fqualname LIKE "%' +
      func + '%";').fetchall():
    print '<h3>%s</h3>' % cgi.escape(f['fqualname'])
    print GetLine(f['file_id'], f['file_line'], f['file_col'])

def processVariable(var):
  for v in conn.execute('SELECT * FROM variables WHERE vname LIKE "%' +
      var + '%";').fetchall():
    qual = v['modifiers'] and v['modifiers'] or ''
    print '<h3>%s %s %s</h3>' % (cgi.escape(qual), cgi.escape(v['vtype']),
      cgi.escape(v['vname']))
    print GetLine(v['file_id'], v['file_line'], v['file_id'])

def processWarnings(warnings, path=None):
  # Check for * which means user entered "warnings:" and wants to see all of them.
  if warnings == '*':
    warnings = ''

  num_warnings = 0
  for w in conn.execute("SELECT file_id, file_line, file_col, (SELECT path FROM files WHERE files.ID=warnings.file_id), wmsg FROM warnings WHERE wmsg LIKE '%" +
      warnings + "%'").fetchall():
    if not path or re.search(path, w[3]):
      print '<h3>%s</h3>' % w[4]
      print GetLine(w[0], w[1], w[2])
      num_warnings += 1
  if num_warnings == 0:
    print '<h3>No warnings found.</h3>'

def processCallers(caller, path=None, funcid=None):
  # I could handle this with a single call, but that gets a bit complicated.
  # Instead, let's first find the function that we're trying to find.
  cur = conn.cursor()
  if funcid is None:
    cur.execute('SELECT *, (SELECT path FROM files WHERE files.ID=functions.file_id) AS file_path FROM functions WHERE fqualname %s' %
      like_escape(caller))
    funcinfos = cur.fetchall()
    if len(funcinfos) == 0:
      print '<h2>No results found</h2>'
      return
    elif len(funcinfos) > 1:
      print '<h3>Ambiguous function:</h3><ul>'
      for funcinfo in funcinfos:
        print ('<li><a href="search.cgi?callers=%s&funcid=%d&tree=%s">%s</a>' +
          ' at %s:%d:%d</li>') % (caller, funcinfo['funcid'], tree,
          funcinfo['fqualname'], funcinfo['file_path'], funcinfo['file_line'], funcinfo['file_col'])
      print '</ul>'
      return
    funcid = funcinfos[0]['funcid']
  # We have two cases: direct calls or we're in targets
  cur = conn.cursor()
  for info in cur.execute(
      "SELECT functions.*, " +
      "(SELECT path FROM files WHERE files.ID=functions.file_id) AS file_path " +
      "FROM functions " +
      "LEFT JOIN callers ON (callers.callerid = funcid) WHERE targetid=? " +
      "UNION SELECT functions.*," +
      "(SELECT path FROM files WHERE files.ID=functions.file_id) AS file_path " +
      "FROM functions LEFT JOIN callers " +
      "ON (callers.callerid = functions.funcid) LEFT JOIN targets USING " +
      "(targetid) WHERE targets.funcid=?", (funcid, funcid)):
    if not path or re.search(path, info['file_path']):
      print '<h3>%s</h3>' % info['fqualname']
      print GetLine(info['file_id'], info['file_line'], info['file_col'])
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
        'or /etc/dxr/dxr.config</h3><p>%s</body>' % msg
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
  conn.execute('SELECT initialize_tokenizer()')
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

# Check whether we automatically redirect to a location
if 'string' in form and 'noredirect' not in form:
  if maybe_redirect(form['string']) is True:
    sys.exit(0)

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
