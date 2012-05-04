import csv
from dxr.languages import register_language_table
from dxr.languages import language_schema
import dxr.plugins
import os
import mmap
import re

file_cache = {}
decl_master = {}
inheritance = {}
calls = {}
overrides = {}

def getFileID(conn, path):
  global file_cache

  file_id = file_cache.get(path)

  if file_id is not None:
    return file_id

  cur = conn.cursor()
  file_id = cur.execute("SELECT ID FROM files where path=?", (path,)).fetchone()

  if file_id is None:
    cur.execute("INSERT INTO files (path) VALUES (?)", (path,))
    file_id = cur.lastrowid

  file_cache[path] = file_id
  return file_id

def splitLoc(conn, value):
  arr = value.split(':')
  return (getFileID(conn, arr[0]), int(arr[1]), int(arr[2]))

def fixupEntryPath(args, file_key, conn, prefix=None):
  value = args[file_key]
  loc = splitLoc(conn, value)

  if prefix is not None:
    prefix = prefix + "_"
  else:
    prefix = ''

  args[prefix + 'file_id'] = loc[0]
  args[prefix + 'file_line'] = loc[1]
  args[prefix + 'file_col'] = loc[2]

def fixupExtent(args, extents_key):
  if extents_key not in args:
    return

  value = args[extents_key]
  arr = value.split(':')

  args['extent_start'] = int(arr[0])
  args['extent_end'] = int(arr[1])
  del args[extents_key]

def getScope(args, conn):
  row = conn.execute("SELECT scopeid FROM scopes WHERE file_id=? AND file_line=? AND file_col=?",
                     (args['file_id'], args['file_line'], args['file_col'])).fetchone()

  if row is not None:
    return row[0]

  return None

def addScope(args, conn, name, id):
  scope = {}
  scope['sname'] = args[name]
  scope['scopeid'] = args[id]
  scope['file_id'] = args['file_id']
  scope['file_line'] = args['file_line']
  scope['file_col'] = args['file_col']
  scope['language'] = 'native'

  stmt = language_schema.get_insert_sql('scopes', scope)
  conn.execute(stmt[0], stmt[1])

def handleScope(args, conn, canonicalize=False):
  scope = {}

  if 'scopename' not in args:
    return

  scope['sname'] = args['scopename']
  scope['scopeloc'] = args['scopeloc']
  scope['language'] = 'native'
  fixupEntryPath(scope, 'scopeloc', conn)

  if canonicalize is True:
    decl = canonicalize_decl(scope['sname'], scope['file_id'], scope['file_line'], scope['file_col'])
    scope['file_id'], scope['file_line'], scope['file_col'] = decl[1], decl[2], decl[3]

  scopeid = getScope(scope, conn)

  if scopeid is None:
    scope['scopeid'] = scopeid = dxr.plugins.next_global_id()
    stmt = language_schema.get_insert_sql('scopes', scope)
    conn.execute(stmt[0], stmt[1])

  if scopeid is not None:
    args['scopeid'] = scopeid

def process_decldef(args, conn):
  # Store declaration map basics on memory
  name, defloc, declloc = args['name'], args['defloc'], args['declloc']
  defid, defline, defcol = splitLoc(conn, args['defloc'])
  declid, declline, declcol = splitLoc (conn, args['declloc'])

  decl_master[(name, declid, declline, declcol)] = (defid, defline, defcol)
  decl_master[(name, defid, defline, defcol)] = (defid, defline, defcol)

  fixupEntryPath(args, 'declloc', conn)
  fixupEntryPath(args, 'defloc', conn, 'definition')
  fixupExtent(args, 'extent')
  
  return schema.get_insert_sql('decldef', args)

def process_type(args, conn):
  fixupEntryPath(args, 'tloc', conn)

  # Scope might have been previously added to satisfy other process_* call
  scopeid = getScope(args, conn)

  if scopeid is not None:
    args['tid'] = scopeid
  else:
    args['tid'] = dxr.plugins.next_global_id()
    addScope(args, conn, 'tname', 'tid')

  handleScope(args, conn)
  fixupExtent(args, 'extent')

  return language_schema.get_insert_sql('types', args)

def process_typedef(args, conn):
  args['tid'] = dxr.plugins.next_global_id()
  fixupEntryPath(args, 'tloc', conn)
  fixupExtent(args, 'extent')
#  handleScope(args, conn)
  return schema.get_insert_sql('typedefs', args)

def process_function(args, conn):
  fixupEntryPath(args, 'floc', conn)
  scopeid = getScope(args, conn)

  if scopeid is not None:
    args['funcid'] = scopeid
  else:
    args['funcid'] = dxr.plugins.next_global_id()
    addScope(args, conn, 'fname', 'funcid')

  if 'overridename' in args:
    overrides[args['funcid']] = (args['overridename'], args['overrideloc'])

  handleScope(args, conn)
  fixupExtent(args, 'extent')
  return language_schema.get_insert_sql('functions', args)

def process_impl(args, conn):
  inheritance[args['tbname'], args['tbloc'], args['tcname'], args['tcloc']] = args
  return None

def process_variable(args, conn):
  args['varid'] = dxr.plugins.next_global_id()
  fixupEntryPath(args, 'vloc', conn)
  handleScope(args, conn)
  fixupExtent(args, 'extent')
  return language_schema.get_insert_sql('variables', args)

def process_ref(args, conn):
  if 'extent' not in args:
    return None

  fixupEntryPath(args, 'refloc', conn)
  fixupEntryPath(args, 'varloc', conn, 'referenced')
  fixupExtent(args, 'extent')

  return schema.get_insert_sql('refs', args)

def process_warning(args, conn):
  fixupEntryPath(args, 'wloc', conn)
  return schema.get_insert_sql('warnings', args)

def process_macro(args, conn):
  args['macroid'] = dxr.plugins.next_global_id()
  if 'macrotext' in args:
    args['macrotext'] = args['macrotext'].replace("\\\n", "\n").strip()
  fixupEntryPath(args, 'macroloc', conn)
  return schema.get_insert_sql('macros', args)

def process_call(args, conn):
  if 'callername' in args:
    calls[args['callername'], args['callerloc'],
          args['calleename'], args['calleeloc']] = args
  else:
    calls[args['calleename'], args['calleeloc']] = args

  return None

def load_indexer_output(fname):
  f = open(fname, "rb")
  try:
    parsed_iter = csv.reader(f)
    for line in parsed_iter:
      # Our first column is the type that we're reading, the others are just
      # an args array to be passed in
      argobj = {}
      for i in range(1, len(line), 2):
        argobj[line[i]] = line[i + 1]
      globals()['process_' + line[0]](argobj)
  except:
    print fname, line
    raise
  finally:
    f.close()

def dump_indexer_output(conn, fname):
  f = open(fname, 'r')
  limit = 0

  try:
    parsed_iter = csv.reader(f)
    for line in parsed_iter:
      args = {}
      # Our first column is the type that we're reading, the others are just
      # a key/value pairs array to be passed in
      for i in range(1, len(line), 2):
        args[line[i]] = line[i + 1]

      stmt = globals()['process_' + line[0]](args, conn)

      if stmt is None:
        continue

      if isinstance(stmt, list):
        for elem in list:
          conn.execute(elem[0], elem[1])
      elif isinstance(stmt, tuple):
        conn.execute(stmt[0], stmt[1])
      else:
        conn.execute(stmt)

      limit = limit + 1

      if limit > 10000:
        limit = 0
        conn.commit()
  except IndexError, e:
    raise e
  finally:
    f.close()

file_names = []
def collect_files(arg, dirname, fnames):
  for name in fnames:
    if os.path.isdir(name): continue
    if not name.endswith(arg): continue
    file_names.append(os.path.join(dirname, name))

def canonicalize_decl(name, id, line, col):
  value = decl_master.get((name, id, line, col), None)

  if value is None:
    return (name, id, line, col)
  else:
    return (name, value[0], value[1], value[2])

def recanon_decl(name, loc):
  decl_master[name, loc] = loc
  return (name, loc)

def fixup_scope(conn):
  print "Fixing up scopes..."
  conn.execute ("UPDATE types SET scopeid = (SELECT scopeid FROM scopes WHERE " +
                "scopes.file_id = types.file_id AND scopes.file_line = types.file_line " +
                "AND scopes.file_col = types.file_col) WHERE scopeid IS NULL")
  conn.execute ("UPDATE functions SET scopeid = (SELECT scopeid from scopes where " +
                "scopes.file_id = functions.file_id AND scopes.file_line = functions.file_line " +
                "AND scopes.file_col = functions.file_col) WHERE scopeid IS NULL")
  conn.execute ("UPDATE variables SET scopeid = (SELECT scopeid from scopes where " +
                "scopes.file_id = variables.file_id AND scopes.file_line = variables.file_line " +
                "AND scopes.file_col = variables.file_col) WHERE scopeid IS NULL")


def build_inherits(base, child, direct):
  db = { 'tbase': base, 'tderived': child }
  if direct is not None:
    db['inhtype'] = direct
  return db

def generate_inheritance(conn):
  childMap, parentMap = {}, {}
  types = {}

  for row in conn.execute("SELECT tqualname, file_id, file_line, file_col, tid from types").fetchall():
    types[(row[0], row[1], row[2], row[3])] = row[4]

  for infoKey in inheritance:
    info = inheritance[infoKey]
    try:
      base_loc = splitLoc(conn, info['tbloc'])
      child_loc = splitLoc(conn, info['tcloc'])

      base = types[canonicalize_decl(info['tbname'], base_loc[0], base_loc[1], base_loc[2])]
      child = types[canonicalize_decl(info['tcname'], child_loc[0], child_loc[1], child_loc[2])]
    except KeyError:
      continue

    conn.execute("INSERT OR IGNORE INTO impl(tbase, tderived, inhtype) VALUES (?, ?, ?)",
                 (base, child, info.get('access', '')))

    # Get all known relations
    subs = childMap.setdefault(child, [])
    supers = parentMap.setdefault(base, [])
    # Use this information
    for sub in subs:
      conn.execute("INSERT OR IGNORE INTO impl(tbase, tderived) VALUES (?, ?)",
                   (base, sub))
      parentMap[sub].append(base)
    for sup in supers:
      conn.execute("INSERT OR IGNORE INTO impl(tbase, tderived) VALUES (?, ?)",
                   (sup, child))
      childMap[sup].append(child)

    # Carry through these relations
    newsubs = childMap.setdefault(base, [])
    newsubs.append(child)
    newsubs.extend(subs)
    newsupers = parentMap.setdefault(child, [])
    newsupers.append(base)
    newsupers.extend(supers)


def generate_callgraph(conn):
  global calls
  functions = {}
  variables = {}
  callgraph = []

  print "Generating callers..."

  for row in conn.execute("SELECT fqualname, file_id, file_line, file_col, funcid FROM functions").fetchall():
    functions[(row[0], row[1], row[2], row[3])] = row[4]

  for row in conn.execute("SELECT vname, file_id, file_line, file_col, varid FROM variables").fetchall():
    variables[(row[0], row[1], row[2], row[3])] = row[4]

  # Generate callers table
  for call in calls.values():
    if 'callername' in call:
      caller_loc = splitLoc(conn, call['callerloc'])
      source = canonicalize_decl(call['callername'], caller_loc[0], caller_loc[1], caller_loc[2])
      call['callerid'] = functions.get(source)

      if call['callerid'] is None:
        continue
    else:
      call['callerid'] = 0

    target_loc = splitLoc(conn, call['calleeloc'])
    target = canonicalize_decl(call['calleename'], target_loc[0], target_loc[1], target_loc[2])
    targetid = functions.get(target)

    if targetid is None:
      targetid = variables.get(target)

    if targetid is not None:
      call['targetid'] = targetid
      callgraph.append(call)

  del variables

  print "Generating targets..."

  # Generate targets table
  overridemap = {}

  for func, funcid in functions.iteritems():
    override = overrides.get(funcid)

    if override is None:
      continue

    override_loc = splitLoc(conn, override[1])
    base = canonicalize_decl(override[0], override_loc[0], override_loc[1], override_loc[2])
    basekey = functions.get(base)

    if basekey is None:
      continue

    overridemap.setdefault(basekey, set()).add(funcid)

  rescan = [x for x in overridemap]
  while len(rescan) > 0:
    base = rescan.pop(0)
    childs = overridemap[base]
    prev = len(childs)
    temp = childs.union(*(overridemap.get(sub, []) for sub in childs))
    childs.update(temp)
    if len(childs) != prev:
      rescan.append(base)

  for base, childs in overridemap.iteritems():
    conn.execute("INSERT OR IGNORE INTO targets (targetid, funcid) VALUES (?, ?)",
                 (-base, base));

    for child in childs:
      conn.execute("INSERT OR IGNORE INTO targets (targetid, funcid) VALUES (?, ?)",
                   (-base, child));

  for call in callgraph:
    if call['calltype'] == 'virtual':
      targetid = call['targetid']
      call['targetid'] = -targetid
      if targetid not in overridemap:
        overridemap[targetid] = set()
        conn.execute("INSERT OR IGNORE INTO targets (targetid, funcid) VALUES (?, ?)",
                     (-targetid, targetid));
    conn.execute("INSERT OR IGNORE INTO callers (callerid, targetid) VALUES (?, ?)",
                  (call['callerid'], call['targetid']))

def update_defids(conn):
  print "Updating definition IDs..."
  conn.execute ("UPDATE decldef SET defid = (" +
                "SELECT tid FROM types WHERE types.file_id = decldef.definition_file_id AND " +
                "types.file_line = decldef.definition_file_line AND types.file_col = decldef.definition_file_col UNION " +
                "SELECT funcid FROM functions WHERE functions.file_id = decldef.definition_file_id AND " +
                "functions.file_line = decldef.definition_file_line AND functions.file_col = decldef.definition_file_col)")

def update_refs(conn):
  print "Updating refs..."
  conn.execute ("UPDATE refs SET refid = ("+
                "SELECT macroid FROM macros WHERE macros.file_id = refs.referenced_file_id AND " +
                "macros.file_line = refs.referenced_file_line AND macros.file_col = refs.referenced_file_col UNION " +
                "SELECT tid from types where types.file_id = refs.referenced_file_id AND " +
                "types.file_line = refs.referenced_file_line AND types.file_col = refs.referenced_file_col UNION " +
                "SELECT funcid FROM functions WHERE functions.file_id = refs.referenced_file_id AND " +
                "functions.file_line = refs.referenced_file_line AND functions.file_col = refs.referenced_file_col UNION " +
                "SELECT defid FROM decldef WHERE decldef.file_id = refs.referenced_file_id AND " +
                "decldef.file_line = refs.referenced_file_line AND decldef.file_col = refs.referenced_file_col UNION " +
                "SELECT varid FROM variables WHERE variables.file_id = refs.referenced_file_id AND " +
                "variables.file_line = refs.referenced_file_line AND variables.file_col = refs.referenced_file_col)")


def post_process(srcdir, objdir):
  return None


def build_database(conn, srcdir, objdir, cache=None):
  count = 0
  os.path.walk(objdir, collect_files, ".csv")

  if file_names == []:
    raise IndexError('No .csv files in %s' % objdir)
  for f in file_names:
    dump_indexer_output(conn, f)
    count = count + 1

    if count % 1000 == 0:
      conn.commit()

  fixup_scope(conn)
  print "Generating callgraph..."
  generate_callgraph(conn)
  print "Generating inheritances..."
  generate_inheritance(conn)
  update_defids(conn)
  update_refs(conn)

  conn.commit()

  return None

def pre_html_process(treecfg, blob):
  return

def sqlify(blob):
  return

def can_use(treecfg):
  # We need to have clang and llvm-config in the path
#  return dxr.plugins.in_path('clang') and dxr.plugins.in_path('llvm-config')
  return True

schema = dxr.plugins.Schema({
  # Typedef information in the tables
  "typedefs": [
    ("tid", "INTEGER", False),           # The typedef's tid (also in types)
    ("ttypedef", "VARCHAR(256)", False), # The long name of the type
    ("extent_start", "INTEGER", True),
    ("extent_end", "INTEGER", True),
    ("_location", True),
    ("_key", "tid"),
    ("_index", "ttypedef")
  ],
  # References to functions, types, variables, etc.
  "refs": [
    ("refid", "INTEGER", True),      # ID of the identifier being referenced
    ("extent_start", "INTEGER", True),
    ("extent_end", "INTEGER", True),
    ("_location", True),
    ("_location", True, 'referenced')
  ],
  # Warnings found while compiling
  "warnings": [
    ("wmsg", "VARCHAR(256)", False), # Text of the warning
    ("_location", True),
  ],
  # Declaration/definition mapping
  "decldef": [
    ("defid", "INTEGER", True),    # ID of the definition instance
    ("_location", True),
    ("_location", True, 'definition'),
    # Extents of the declaration
    ("extent_start", "INTEGER", True),
    ("extent_end", "INTEGER", True)
  ],
  # Macros: this is a table of all of the macros we come across in the code.
  "macros": [
    ("macroid", "INTEGER", False),        # The macro id, for references
    ("macroname", "VARCHAR(256)", False), # The name of the macro
    ("macroargs", "VARCHAR(256)", True),  # The args of the macro (if any)
    ("macrotext", "TEXT", True),          # The macro contents
    ("_location", True)
  ],
  # The following two tables are combined to form the callgraph implementation.
  # In essence, the callgraph can be viewed as a kind of hypergraph, where the
  # edges go from functions to sets of functions and variables. For use in the
  # database, we are making some big assumptions: the targetid is going to be
  # either a function or variable (the direct thing we called); if the function
  # is virtual or the target is a variable, we use the targets table to identify
  # what the possible implementations could be.
  "callers": [
    ("callerid", "INTEGER", False), # The function in which the call occurs
    ("targetid", "INTEGER", False), # The target of the call
    ("_key", "callerid", "targetid"),
    ("_fkey", "callerid", "functions", "funcid")
  ],
  "targets": [
    ("targetid", "INTEGER", False), # The target of the call
    ("funcid", "INTEGER", False),   # One of the functions in the target set
    ("_key", "targetid", "funcid"),
    ("_fkey", "targetid", "functions", "funcid")
  ]
})

get_schema = dxr.plugins.make_get_schema_func(schema)

import dxr
from dxr.tokenizers import CppTokenizer
class CxxHtmlifier:
  def __init__(self, blob, srcpath, treecfg, conn):
    self.srcpath = srcpath.replace(treecfg.sourcedir + '/', '')
    self.blob_file = None #blob["byfile"].get(self.srcpath, None)
    self.conn = conn

  def collectSidebar(self):
    def make_tuple(df, name, loc, scope="scopeid", decl=False, srcpath=None):
      if decl:
        img = 'images/icons/page_white_code.png'
      else:
        img = 'images/icons/page_white_wrench.png'

      try:
        sname = df['sname']
      except:
        sname = None
        pass

      try:
        path = df['path']
        if path == srcpath:
          path = None
      except:
        path = None
        pass

      if sname is not None and (len(sname) == 0 or sname == name):
        sname = None

      return (df[name], df[loc], df[name], img, sname, path)
    for row in self.conn.execute("SELECT tqualname, file_line, scopeid, (SELECT sname from scopes where scopes.scopeid = types.scopeid) AS sname " +
                                 "FROM types WHERE file_id = (SELECT id FROM files where path = ?)", (self.srcpath,)).fetchall():
      yield make_tuple(row, "tqualname", "file_line", "scopeid")
    for row in self.conn.execute("SELECT fqualname, file_line, scopeid, (SELECT sname from scopes where scopes.scopeid = f1.scopeid) AS sname, " +
                                 "(SELECT path from files where id=f1.file_id) AS path FROM functions f1 WHERE funcid IN " +
                                 "(SELECT coalesce((SELECT defid FROM decldef dd WHERE dd.file_id = f2.file_id AND dd.file_line = f2.file_line " +
                                 " AND dd.file_col = f2.file_col), f2.funcid) FROM functions f2 " +
                                 "WHERE f2.file_id = (SELECT id FROM files WHERE path = ?))", (self.srcpath,)).fetchall():
      yield make_tuple(row, "fqualname", "file_line", "scopeid", False, self.srcpath)

    for row in self.conn.execute("SELECT vname, file_line, scopeid, (SELECT sname from scopes where scopes.scopeid = variables.scopeid) AS sname " +
                                 "FROM variables WHERE file_id = (SELECT id FROM files WHERE path = ?) AND " +
                                 "scopeid NOT IN (SELECT funcid FROM functions WHERE functions.file_id = variables.file_id UNION " +
                                 "  SELECT defid FROM decldef WHERE decldef.file_id = variables.file_id)",
                                 (self.srcpath,)).fetchall():
      yield make_tuple(row, "vname", "file_line", "scopeid")

    tblmap = { "functions": "fqualname", "types": "tqualname" }
#    for df in self.blob_file["decldef"]:
#      table = df["table"]
#      if table in tblmap:
#        yield make_tuple(dxr.languages.get_row_for_id(table, df["defid"]), tblmap[table],
#          df["declloc"], "scopeid", True)
    for row in self.conn.execute("SELECT macroname, file_line FROM macros WHERE file_id = (SELECT id FROM files WHERE path = ?)", (self.srcpath,)).fetchall():
      yield make_tuple(row, "macroname", "file_line")

  def getSyntaxRegions(self):
    for token in self.tokenizer.getTokens():
      if token.token_type == self.tokenizer.KEYWORD:
        yield (token.start, token.end, 'k')
      elif token.token_type == self.tokenizer.STRING:
        yield (token.start, token.end, 'str')
      elif token.token_type == self.tokenizer.COMMENT:
        yield (token.start, token.end, 'c')
      elif token.token_type == self.tokenizer.PREPROCESSOR:
        yield (token.start, token.end, 'p')

  def getLinkRegions(self):
    def make_link(obj, clazz, rid):
      start = obj['extent_start']
      end = obj['extent_end']
      kwargs = {}
      kwargs['rid'] = rid
      kwargs['class'] = clazz
      return (start, end, kwargs)

    pattern = re.compile('\#[\s]*include[\s]*[<"](\S+)[">]')

    for token in self.tokenizer.getTokens():
      if token.token_type == self.tokenizer.PREPROCESSOR and 'include' in token.name:
        match = pattern.match (token.name)
        if match is None:
          continue
        rows = self.conn.execute("SELECT path FROM files WHERE path LIKE ?", ("%%%s" % (match.group(1)),)).fetchall()

        if rows is not None and len(rows) == 1:
          yield (token.start + match.start(1), token.start + match.end(1), {"href" : rows[0][0] })
      else:
        continue

    for row in self.conn.execute("SELECT refid, extent_start, extent_end FROM refs WHERE file_id = (SELECT id FROM files WHERE path = ?) ORDER BY extent_start", (self.srcpath,)).fetchall():
      yield make_link(row, "ref", row['refid'])

    for row in self.conn.execute("SELECT varid, extent_start, extent_end FROM variables WHERE file_id = (SELECT id FROM files WHERE path = ?) ORDER BY extent_start", (self.srcpath,)).fetchall():
      yield make_link(row, "var", row['varid'])

    for row in self.conn.execute("SELECT funcid, extent_start, extent_end FROM functions WHERE file_id = (SELECT id FROM files WHERE path = ?) ORDER BY extent_start", (self.srcpath,)).fetchall():
      yield make_link(row, "func", row['funcid'])

    for row in self.conn.execute("SELECT tid, extent_start, extent_end FROM types WHERE file_id = (SELECT id FROM files WHERE path = ?) ORDER BY extent_start", (self.srcpath,)).fetchall():
      yield make_link(row, "t", row['tid'])

    for row in self.conn.execute("SELECT tid, extent_start, extent_end FROM typedefs WHERE file_id = (SELECT id FROM files WHERE path = ?) ORDER BY extent_start", (self.srcpath,)).fetchall():
      yield make_link(row, "t", row['tid'])

    for row in self.conn.execute("SELECT macroid, macroname, file_line, file_col FROM macros WHERE file_id = (SELECT id FROM files WHERE path = ?)", (self.srcpath,)).fetchall():
      line = row['file_line']
      col = row['file_col']
      yield ((line, col), (line, col + len(row['macroname'])),
        {'class': 'm', 'rid': row['macroid']})

  def getLineAnnotations(self):
    for row in self.conn.execute("SELECT wmsg, file_line FROM warnings WHERE file_id = (SELECT id FROM files WHERE path = ?)", (self.srcpath,)).fetchall():
      yield (row[1], {"class": "lnw", "title": row[0]})

htmlifier_current = None
htmlifier_current_path = None

def ensureHtmlifier(blob, srcpath, treecfg, conn=None, dbpath=None):
  global htmlifier_current_path
  global htmlifier_current

  if srcpath != htmlifier_current_path:
    htmlifier_current_path = srcpath

    if dbpath is None:
      dbpath = srcpath

    htmlifier_current = CxxHtmlifier(blob, dbpath, treecfg, conn)
    htmlifier_current.tokenizer = CppTokenizer(dxr.readFile(srcpath))

  return htmlifier_current

def get_sidebar_links(blob, srcpath, treecfg, conn=None, dbpath=None):
  htmlifier = ensureHtmlifier(blob, srcpath, treecfg, conn, dbpath)
  return htmlifier.collectSidebar()
def get_link_regions(blob, srcpath, treecfg, conn=None, dbpath=None):
  htmlifier = ensureHtmlifier(blob, srcpath, treecfg, conn, dbpath)
  return htmlifier.getLinkRegions()
def get_line_annotations(blob, srcpath, treecfg, conn=None, dbpath=None):
  htmlifier = ensureHtmlifier(blob, srcpath, treecfg, conn, dbpath)
  return htmlifier.getLineAnnotations()
def get_syntax_regions(blob, srcpath, treecfg, conn=None, dbpath=None):
  htmlifier = ensureHtmlifier(blob, srcpath, treecfg, conn, dbpath)
  return htmlifier.getSyntaxRegions()

htmlifier = {}
for f in ('.c', '.cc', '.cpp', '.h', '.hpp'):
  htmlifier[f] = {'get_sidebar_links': get_sidebar_links,
      'get_link_regions': get_link_regions,
      'get_line_annotations': get_line_annotations,
      'get_syntax_regions': get_syntax_regions}

  if f[1] == 'c':
    htmlifier[f]['get_inhibit_sidebar'] = True

def get_htmlifiers():
  return htmlifier

__all__ = dxr.plugins.required_exports()
