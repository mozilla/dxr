import csv
import dxr.plugins
import os

# Unlike the native code, we index here by interface name, since that is a unit
# that we use in the xpt reflection and is guaranteed to be unique. It's also
# similar.

interfaces = {}
attributes = {}
methods = {}
consts = {}
def process_interface(info):
  interfaces[info['name']] = info
def process_attr(info):
  attributes[info['iface'], info['name']] = info
def process_method(info):
  methods[info['iface'], info['name']] = info
def process_const(info):
  consts[info['iface'], info['name']] = info

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
  except IndexError, e:
    print line
    raise e
  finally:
    f.close()

location_keys = {
  'interfaces': 'iloc',
  'attributes': 'loc',
  'methods': 'loc',
  'consts': 'loc'
}

def post_process(srcdir, objdir):
  file_names = []
  def collect_files(arg, dirname, fnames):
    for name in fnames:
      if os.path.isdir(name): continue
      if not name.endswith(arg): continue
      file_names.append(os.path.join(dirname, name))
  os.path.walk(objdir, collect_files, ".idlcsv")
  for f in file_names:
    load_indexer_output(f)

  blob = {}
  blob["interfaces"] = {}
  for iface in interfaces:
    blob["interfaces"][iface] = interfaces[iface]
    interfaces[iface]["iid"] = dxr.plugins.next_global_id()
  tblmap = {
    "attributes": "attrid",
    "methods": "funcid",
    "consts": "constid"
  }
  for table in tblmap:
    blob[table] = {}
    things = globals()[table]
    for thing, tinfo in things.iteritems():
      id = dxr.plugins.next_global_id()
      blob[table][id] = tinfo
      tinfo[tblmap[table]] = id
      tinfo["iid"] = interfaces[tinfo["iface"]]["iid"]
  for tblname, lockey in location_keys.iteritems():
    # Fix absolute/relative path issues
    for row in blob[tblname].itervalues():
      parts = row[lockey].split(":")
      parts[0] = os.path.relpath(parts[0], srcdir)
      row[lockey] = ':'.join(parts)
  return blob

def pre_html_process(treecfg, blob):
  blob["byfile"] = dxr.plugins.break_into_files(blob, location_keys)

def can_use(treecfg):
  # Don't know? just guess!
  if treecfg is None:
    return True
  # This is a hack for being a mozilla tree: $srcdir/config/rules.mk
  if os.path.exists(os.path.join(treecfg.sourcedir, 'config', 'rules.mk')):
    return True
  return False

file_cache = {}

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


def build_database(conn, srcdir, objdir, cache=None):
  for iface, info in interfaces.iteritems():
    loc = info['iloc'].split(':')

    if len(loc) != 2:
      continue

    file_id = getFileID(conn,loc[0])
    conn.execute("UPDATE OR IGNORE types SET file_id = ?, file_line = ?," +
                 "file_col=0, tkind='interface' WHERE tname = ?",
                 (file_id, int(loc[1]), info['name']))

  conn.commit()

schema = dxr.plugins.Schema({
  # Scope definitions: a scope is anything that is both interesting (i.e., not
  # a namespace) and can contain other objects. The IDs for this scope should be
  # IDs in other tables as well; the table its in can disambiguate which type of
  # scope you're looking at.
  "interfaces": [
    ("iid", "INTEGER", False),
    ("iname", "VARCHAR(256)", True),
    ("iloc", "_location", True),
    ("uuid", "CHAR(33)", True),
    ("attributes", "VARCHAR(256)", True),
    ("_key", "iid")
  ],
  # Inheritance relations: note that we store the full transitive closure in
  # this table, so if A extends B and B extends C, we'd have (A, C) stored in
  # the table as well; this is necessary to make SQL queries work, since there's
  # no "transitive closure lookup expression".
  "idlimpl": [
    ("tbase", "INTEGER", False),      # tid of base type
    ("tderived", "INTEGER", False),   # tid of derived type
    ("inhtype", "VARCHAR(32)", True), # Type of inheritance; NULL is indirect
    ("_key", "tbase", "tderived")
  ],
  # Functions: the functions or operators of an interface.
  "idlfunctions": [
    ("funcid", "INTEGER", False),         # Function ID
    ("iid", "INTEGER", False),            # Interface defined in
    ("fname", "VARCHAR(256)", False),     # Short name (no args)
    ("flongname", "VARCHAR(512)", False), # Fully qualified name, including args
    ("floc", "_location", True),          # Location of definition
    ("modifiers", "VARCHAR(256)", True),  # Modifiers (e.g., private)
    ("_key", "funcid")
  ],
  # Variables: class, global, local, enum constants; they're all in here
  # Variables are of course not scopes, but for ease of use, they use IDs from
  # the same namespace, no scope will have the same ID as a variable and v.v.
  "idlattrs": [
    ("attrid", "INTEGER", False),        # Variable ID
    ("iid", "INTEGER", False),           # Interface defined in
    ("attrname", "VARCHAR(256)", False), # Short name
    ("attrloc", "_location", True),      # Location of definition
    ("attrtype", "VARCHAR(256)", True),  # Full type (including pointer stuff)
    ("modifiers", "VARCHAR(256)", True), # Modifiers for the declaration
    ("_key", "attrid")
  ]
})

#get_schema = dxr.plugins.make_get_schema_func(schema)
get_schema = lambda : ''

from ply import lex

class IdlLexer(object):
  keywords = dict([(x, 'KEYWORD') for x in ['attribute', 'boolean', 'const',
    'double', 'float', 'implements', 'in', 'interface', 'long', 'octet',
    'raises', 'sequence', 'short', 'typedef', 'unsigned', 'void', 'readonly',
    'out', 'inout', 'readonly', 'native', 'string', 'wstring', 'char',
    'wchar']])

  tokens = ['KEYWORD', 'COMMENT', 'IDENTIFIER', 'NUMBER', 'INCLUDE', 'CODEFRAG']
  literals = '"(){}[],;:=|+-*<>'
  t_ignore = ' \t\n\r'

  t_COMMENT = r'(?m)//.*?$|/\*(?s).*?\*/'
  def t_IDENTIFIER(self, t):
    r'[A-Za-z_][A-Za-z0-9]*'
    t.type = t.value in self.keywords and 'KEYWORD' or 'IDENTIFIER'
    return t
  t_NUMBER = r'-?(?:0(?:[0-7]*|[Xx][0-9A-Fa-f]+)|[1-9][0-9]*)'
  t_INCLUDE = r'\#include[ \t]+"[^"\n]+"'
  t_CODEFRAG = '(?s)%{[^\n]*\n.*?\n%}[^\n]*$'

  def t_error(self, err):
    pass
  def __init__(self, source):
    self.lexer = lex.lex(object=self)
    self.lexer.input(source)

  def token(self):
    return self.lexer.token()

import dxr
class IdlHtmlifier:
  def __init__(self, blob, srcpath, treecfg):
    self.source = dxr.readFile(srcpath)
    self.srcpath = srcpath.replace(treecfg.sourcedir + '/', '')
    self.blob_file = blob["byfile"].get(self.srcpath, None)
    self.blob = blob

  def collectSidebar(self):
    if self.blob_file is None:
      return
    def make_tuple(df, name, loc):
      img = 'images/icons/page_white_wrench.png'
      if 'iface' in df and df['iface'] > 0:
        return (df[name], df[loc].split(':')[1], df[name], img,
          self.blob["interfaces"][df['iface']]["name"])
      return (df[name], df[loc].split(':')[1], df[name], img)
    for df in self.blob_file["interfaces"]:
      yield make_tuple(df, "name", "iloc")
    for df in self.blob_file["attributes"]:
      yield make_tuple(df, "name", "loc")
    for df in self.blob_file["consts"]:
      yield make_tuple(df, "name", "loc")
    for df in self.blob_file["methods"]:
      yield make_tuple(df, "name", "loc")

  def getSyntaxRegions(self):
    self.tokenizer = IdlLexer(self.source)
    while True:
      tok = self.tokenizer.token()
      if not tok: break
      if tok.type == 'KEYWORD':
        yield (tok.lexpos, tok.lexpos + len(tok.value), 'k')
      elif tok.type == 'COMMENT':
        yield (tok.lexpos, tok.lexpos + len(tok.value), 'c')
      elif tok.type == 'NUMBER':
        yield (tok.lexpos, tok.lexpos + len(tok.value), 'str')
      elif tok.type == 'INCLUDE':
        yield (tok.lexpos, tok.lexpos + len(tok.value), 'p')

  def getLinkRegions(self):
    if self.blob_file is None:
      return
    def make_link(obj, loc, name, clazz, **kwargs):
      line, col = obj[loc].split(':')[1:]
      line, col = int(line), int(col)
      kwargs['class'] = clazz
      kwargs['line'] =  line
      return ((line, col), (line, col + len(obj[name])), kwargs)
    for df in self.blob_file["variables"]:
      yield make_link(df, 'vloc', 'vname', 'var', rid=df['varid'])
    for df in self.blob_file["functions"]:
      yield make_link(df, 'floc', 'fname', 'func', rid=df['funcid'])
    for df in self.blob_file["types"]:
      yield make_link(df, 'tloc', 'tqualname', 't', rid=df['tid'])
    for df in self.blob_file["refs"]:
      start, end = df["extent"].split(':')
      yield (int(start), int(end), {'class': 'ref', 'rid': df['refid']})

def get_sidebar_links(blob, srcpath, treecfg, conn=None, dbpath=None):
  if srcpath not in htmlifier_store:
    htmlifier_store[srcpath] = IdlHtmlifier(blob, srcpath, treecfg)
  return htmlifier_store[srcpath].collectSidebar()
def get_link_regions(blob, srcpath, treecfg, conn=None, dbpath=None):
  if srcpath not in htmlifier_store:
    htmlifier_store[srcpath] = IdlHtmlifier(blob, srcpath, treecfg)
  return htmlifier_store[srcpath].getLinkRegions()
def get_syntax_regions(blob, srcpath, treecfg, conn=None, dbpath=None):
  if srcpath not in htmlifier_store:
    htmlifier_store[srcpath] = IdlHtmlifier(blob, srcpath, treecfg)
  return htmlifier_store[srcpath].getSyntaxRegions()
htmlifier_store = {}

htmlifier = {
  '.idl': {'get_sidebar_links': get_sidebar_links,
    #'get_link_regions': get_link_regions,
    'get_syntax_regions': get_syntax_regions
  }
}

def get_htmlifiers():
  return htmlifier

__all__ = dxr.plugins.required_exports()
