import csv
import dxr.plugins
import os

decl_master = {}
types = {}
typedefs = {}
functions = {}
inheritance = {}
variables = {}
references = {}
warnings = []
macros = {}

def process_decldef(args):
  name, defloc, declloc = args['name'], args['defloc'], args['declloc']
  decl_master[(name, declloc)] = defloc
  decl_master[(name, defloc)] = defloc

def process_type(typeinfo):
  types[(typeinfo['tqualname'], typeinfo['tloc'])] = typeinfo

def process_typedef(typeinfo):
  typedefs[(typeinfo['tqualname'], typeinfo['tloc'])] = typeinfo
  typeinfo['tkind'] = 'typedef'

def process_function(funcinfo):
  functions[(funcinfo['fqualname'], funcinfo['floc'])] = funcinfo

def process_impl(info):
  inheritance[info['tbname'], info['tbloc'], info['tcname'], info['tcloc']]=info

def process_variable(varinfo):
  variables[varinfo['vname'], varinfo['vloc']] = varinfo

def process_ref(info):
  # Each reference is pretty much unique, but we might record it several times
  # due to header files.
  references[info['varname'], info['varloc'], info['refloc']] = info

def process_warning(warning):
  warnings.append(warning)

def process_macro(macro):
  macros[macro['macroname'], macro['macroloc']] = macro
  if 'macrotext' in macro:
    macro['macrotext'] = macro['macrotext'].replace("\\\n", "\n").strip()

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

file_names = []
def collect_files(arg, dirname, fnames):
  for name in fnames:
    if os.path.isdir(name): continue
    if not name.endswith(arg): continue
    file_names.append(os.path.join(dirname, name))

def make_blob():
  def canonicalize_decl(name, loc):
    return (name, decl_master.get((name, loc), loc))
  def recanon_decl(name, loc):
    decl_master[name, loc] = (name, loc)
    return (name, loc)

  # Produce all scopes
  scopes = {}
  nextIndex = 1
  typeKeys = set()
  for t in types:
    key = canonicalize_decl(t[0], t[1])
    if key not in types:
      key = recanon_decl(t[0], t[1])
    if key not in scopes:
      typeKeys.add(key)
      types[key]['tid'] = scopes[key] = nextIndex
      nextIndex += 1
  # Typedefs need a tid, but they are not a scope
  for t in typedefs:
    typedefs[t]['tid'] = nextIndex
    nextIndex += 1
  funcKeys = set()
  for f in functions:
    key = canonicalize_decl(f[0], f[1])
    if key not in functions:
      key = recanon_decl(f[0], f[1])
    if key not in scopes:
      funcKeys.add(key)
      functions[key]['funcid'] = scopes[key] = nextIndex
      nextIndex += 1

  # Variables aren't scoped, but we still need to refer to them in the same
  # manner, so we'll unify variables with the scope ids
  varKeys = {}
  for v in variables:
    key = (v[0], v[1])
    if key not in varKeys:
      varKeys[key] = variables[v]['varid'] = nextIndex
      nextIndex += 1

  for m in macros:
    macros[m]['macroid'] = nextIndex
    nextIndex += 1

  # Scopes are now defined, this allows us to modify structures for sql prep

  # Inheritance:
  # We need to canonicalize the types and then set up the inheritance tree
  # Since we don't know which order we'll see the pairs, we have to propagate
  # bidirectionally when we find out more.
  def build_inherits(base, child, direct):
    db = { 'tbase': base, 'tderived': child }
    if direct is not None:
      db['inhtype'] = direct
    return db

  childMap, parentMap = {}, {}
  inheritsTree = []
  for infoKey in inheritance:
    info = inheritance[infoKey]
    try:
      base = types[canonicalize_decl(info['tbname'], info['tbloc'])]['tid']
      child = types[canonicalize_decl(info['tcname'], info['tcloc'])]['tid']
    except KeyError:
      continue
    inheritsTree.append(build_inherits(base, child, info['access']))

    # Get all known relations
    subs = childMap.setdefault(child, [])
    supers = parentMap.setdefault(base, [])
    inheritsTree.extend([build_inherits(base, sub, None) for sub in subs])
    inheritsTree.extend([build_inherits(sup, child, None) for sup in supers])

    # Carry through these relations
    newsubs = childMap.setdefault(base, [])
    newsubs.append(child)
    newsubs.extend(subs)
    newsupers = parentMap.setdefault(child, [])
    newsupers.append(base)
    newsupers.extend(supers)

  # Fix up (name, loc) pairs to ids
  def repairScope(info):
    if 'scopename' in info:
      info['scopeid'] = scopes[canonicalize_decl(info.pop('scopename'),
        info.pop('scopeloc'))]
    else:
      info['scopeid'] = 0

  for tkey in typeKeys:
    repairScope(types[tkey])

  for tkey in typedefs:
    repairScope(typedefs[tkey])

  for fkey in funcKeys:
    repairScope(functions[fkey])

  for vkey in varKeys:
    repairScope(variables[vkey])
  
  # dicts can't be stuffed in sets, and our key is very unwieldy. Since
  # duplicates are most likely to occur only when we include the same header
  # file multiple times, the same definition should be used each time, so they
  # should be equivalent pre-canonicalization
  refs = []
  for rkey in references:
    ref = references[rkey]
    canon = canonicalize_decl(ref.pop('varname'), ref.pop('varloc'))
    if canon in varKeys:
      ref['refid'] = varKeys[canon]
      refs.append(ref)
    elif canon in funcKeys:
      ref['refid'] = functions[canon]['funcid']
      refs.append(ref)
    elif canon in typeKeys:
      ref['refid'] = types[canon]['tid']
      refs.append(ref)
    elif canon in typedefs:
      ref['refid'] = typedefs[canon]['tid']
      refs.append(ref)
    elif canon in macros:
      ref['refid'] = macros[canon]['macroid']
      refs.append(ref)

  # Declaration-definition remapping
  decldef = []
  for decl in decl_master:
    defn = (decl[0], decl_master[decl])
    if defn != decl:
      tmap = [ ('types', types, 'tid'), ('functions', functions, 'funcid'),
        ('types', typedefs, 'tid'), ('variables', variables, 'varid') ]
      for tblname, tbl, key in tmap:
        if defn in tbl:
          decldef.append({"declloc": decl[1], "defid": tbl[defn][key],
            "table": tblname})
          break

  # Ball it up for passing on
  blob = {}
  def mdict(info, key):
    return (info[key], info)
  blob["scopes"] = dict([mdict({"scopeid": scopes[s], "sname": s[0],
    "sloc": s[1]}, "scopeid") for s in scopes])
  blob["functions"] = dict([mdict(functions[f], "funcid") for f in funcKeys])
  blob["variables"] = dict([mdict(variables[v], "varid") for v in varKeys])
  blob["types"] = [types[t] for t in typeKeys]
  blob["types"] += [typedefs[t] for t in typedefs]
  blob["impl"] = inheritsTree
  blob["refs"] = refs
  blob["warnings"] = warnings
  blob["decldef"] = decldef
  blob["macros"] = macros
  return blob

def post_process(srcdir, objdir):
  os.path.walk(objdir, collect_files, ".csv")
  for f in file_names:
    load_indexer_output(f)
  blob = make_blob()
  
  # Reindex everything by file
  def schema():
    return { "scopes": [], "functions": [], "variables": [], "types": [],
      "refs": [], "warnings": [], "decldef": [], "macros": [] }
  files = {}
  def add_to_files(table, loc):
    iskey = isinstance(blob[table], dict)
    for row in blob[table]:
      if iskey:
        row = blob[table][row]
      f = row[loc].split(":")[0]
      files.setdefault(f, schema())[table].append(row)
  add_to_files("scopes", "sloc")
  add_to_files("functions", "floc")
  add_to_files("variables", "vloc")
  add_to_files("types", "tloc")
  add_to_files("refs", "refloc")
  add_to_files("warnings", "wloc")
  add_to_files("decldef", "declloc")
  add_to_files("macros", "macroloc")

  # Normalize path names
  blob["byfile"] = {}
  while len(files) > 0:
    f, oldtbl = files.popitem()
    real = os.path.relpath(os.path.realpath(os.path.join(srcdir, f)), srcdir)
    realtbl = blob["byfile"].setdefault(real, schema())
    for table in oldtbl:
      realtbl[table].extend(oldtbl[table])
  return blob

def sqlify(blob):
  return schema.get_data_sql(blob)

def can_use(treecfg):
  # We need to have clang and llvm-config in the path
  return dxr.plugins.in_path('clang') and dxr.plugins.in_path('llvm-config')

schema = dxr.plugins.Schema({
  # Scope definitions: a scope is anything that is both interesting (i.e., not
  # a namespace) and can contain other objects. The IDs for this scope should be
  # IDs in other tables as well; the table its in can disambiguate which type of
  # scope you're looking at.
  "scopes": [
    ("scopeid", "INTEGER", False),   # An ID for this scope
    ("sname", "VARCHAR(256)", True), # Name of the scope
    ("sloc", "_location", True),     # Location of the canonical decl
    ("_key", "scopeid")
  ],
  # Type definitions: anything that defines a type per the relevant specs.
  "types": [
    ("tid", "INTEGER", False),            # Unique ID for the type
    ("scopeid", "INTEGER", False),        # Scope this type is defined in
    ("tname", "VARCHAR(256)", False),     # Simple name of the type
    ("tqualname", "VARCHAR(256)", False), # Fully-qualified name of the type
    ("tloc", "_location", False),         # Location of canonical decl
    ("tkind", "VARCHAR(32)", True),       # Kind of type (e.g., class, union)
    ("_key", "tid")
  ],
  # Inheritance relations: note that we store the full transitive closure in
  # this table, so if A extends B and B extends C, we'd have (A, C) stored in
  # the table as well; this is necessary to make SQL queries work, since there's
  # no "transitive closure lookup expression".
  "impl": [
    ("tbase", "INTEGER", False),      # tid of base type
    ("tderived", "INTEGER", False),   # tid of derived type
    ("inhtype", "VARCHAR(32)", True), # Type of inheritance; NULL is indirect
    ("_key", "tbase", "tderived")
  ],
  # Functions: functions, methods, constructors, operator overloads, etc.
  "functions": [
    ("funcid", "INTEGER", False),         # Function ID (also in scopes)
    ("scopeid", "INTEGER", False),        # Scope defined in
    ("fname", "VARCHAR(256)", False),     # Short name (no args)
    ("fqualname", "VARCHAR(512)", False), # Fully qualified name, excluding args
    ("fargs", "VARCHAR(256)", False),     # Argument vector
    ("ftype", "VARCHAR(256)", False),     # Full return type, as a string
    ("floc", "_location", True),          # Location of definition
    ("modifiers", "VARCHAR(256)", True),  # Modifiers (e.g., private)
    ("_key", "funcid")
  ],
  # Variables: class, global, local, enum constants; they're all in here
  # Variables are of course not scopes, but for ease of use, they use IDs from
  # the same namespace, no scope will have the same ID as a variable and v.v.
  "variables": [
    ("varid", "INTEGER", False),         # Variable ID
    ("scopeid", "INTEGER", False),       # Scope defined in
    ("vname", "VARCHAR(256)", False),    # Short name
    ("vloc", "_location", True),         # Location of definition
    ("vtype", "VARCHAR(256)", True),     # Full type (including pointer stuff)
    ("modifiers", "VARCHAR(256)", True), # Modifiers for the declaration
    ("_key", "varid")
  ],
  # References to functions, types, variables, etc.
  "refs": [
    ("refid", "INTEGER", False),      # ID of the identifier being referenced
    ("refloc", "_location", False),   # Location of the reference
    ("extent", "VARCHAR(30)", False), # Extent (start:end) of the reference
    ("_key", "refid", "refloc")
  ],
  # Warnings found while compiling
  "warnings": {
    "wloc": ("_location", False),   # Location of the warning
    "wmsg": ("VARCHAR(256)", False) # Text of the warning
  },
  # Declaration/definition mapping
  "decldef": {
    "defid": ("INTEGER", False),    # ID of the definition instance
    "declloc": ("_location", False) # Location of the declaration
  },
  # Macros: this is a table of all of the macros we come across in the code.
  "macros": [
     ("macroid", "INTEGER", False),        # The macro id, for references
     ("macroloc", "_location", False),     # The macro definition
     ("macroname", "VARCHAR(256)", False), # The name of the macro
     ("macroargs", "VARCHAR(256)", True),  # The args of the macro (if any)
     ("macrotext", "TEXT", True),          # The macro contents
     ("_key", "macroid", "macroloc"),
  ]
})

get_schema = dxr.plugins.make_get_schema_func(schema)

import dxr
from dxr.tokenizers import CppTokenizer
class CxxHtmlifier:
  def __init__(self, blob, srcpath, treecfg):
    self.source = dxr.readFile(srcpath)
    self.srcpath = srcpath.replace(treecfg.sourcedir + '/', '')
    self.blob_file = blob["byfile"].get(self.srcpath, None)
    self.blob = blob

  def collectSidebar(self):
    if self.blob_file is None:
      return
    def line(linestr):
      return linestr.split(':')[1]
    def make_tuple(df, name, loc, scope="scopeid", decl=False):
      if decl:
        img = 'images/icons/page_white_code.png'
      else:
        loc = df[loc]
        img = 'images/icons/page_white_wrench.png'
      if scope in df and df[scope] > 0:
        return (df[name], loc.split(':')[1], df[name], img,
          self.blob["scopes"][df[scope]]["sname"])
      return (df[name], loc.split(':')[1], df[name], img)
    for df in self.blob_file["types"]:
      yield make_tuple(df, "tqualname", "tloc", "scopeid")
    for df in self.blob_file["functions"]:
      yield make_tuple(df, "fqualname", "floc", "scopeid")
    for df in self.blob_file["variables"]:
      if "scopeid" in df and df["scopeid"] in self.blob["functions"]:
        continue
      yield make_tuple(df, "vname", "vloc", "scopeid")
    tblmap = { "functions": "fqualname", "types": "tqualname" }
    for df in self.blob_file["decldef"]:
      table = df["table"]
      if table in tblmap:
        yield make_tuple(self.blob[table][df["defid"]], tblmap[table],
          df["declloc"], "scopeid", True)
    for df in self.blob_file["macros"]:
      yield make_tuple(df, "macroname", "macroloc")

  def getSyntaxRegions(self):
    self.tokenizer = CppTokenizer(self.source)
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
    if self.blob_file is None:
      return
    def make_link(obj, loc, name, clazz, **kwargs):
      if 'extent' in obj:
        start, end = obj['extent'].split(':')
        start, end = int(start), int(end)
      else:
        line, col = obj[loc].split(':')[1:]
        line, col = int(line), int(col)
        start = line, col
        end = line, col + len(obj[name])
        kwargs['line'] =  line
      kwargs['class'] = clazz
      return (start, end, kwargs)
    for df in self.blob_file["variables"]:
      yield make_link(df, 'vloc', 'vname', 'var', rid=df['varid'])
    for df in self.blob_file["functions"]:
      yield make_link(df, 'floc', 'fname', 'func', rid=df['funcid'])
    for df in self.blob_file["types"]:
      yield make_link(df, 'tloc', 'tqualname', 't', rid=df['tid'])
    for df in self.blob_file["macros"]:
      yield make_link(df, "macroloc", "macroname", "m", rid=df['macroid'])
    for df in self.blob_file["refs"]:
      if "extent" in df:
        start, end = df["extent"].split(':')
        yield (int(start), int(end), {'class': 'ref', 'rid': df['refid']})

  def getLineAnnotations(self):
    if self.blob_file is None:
      return
    for warn in self.blob_file["warnings"]:
      line = int(warn["wloc"].split(":")[1])
      yield (line, {"class": "lnw", "title": warn["wmsg"]})

def get_sidebar_links(blob, srcpath, treecfg):
  if srcpath not in htmlifier_store:
    htmlifier_store[srcpath] = CxxHtmlifier(blob, srcpath, treecfg)
  return htmlifier_store[srcpath].collectSidebar()
def get_link_regions(blob, srcpath, treecfg):
  if srcpath not in htmlifier_store:
    htmlifier_store[srcpath] = CxxHtmlifier(blob, srcpath, treecfg)
  return htmlifier_store[srcpath].getLinkRegions()
def get_line_annotations(blob, srcpath, treecfg):
  if srcpath not in htmlifier_store:
    htmlifier_store[srcpath] = CxxHtmlifier(blob, srcpath, treecfg)
  return htmlifier_store[srcpath].getLineAnnotations()
def get_syntax_regions(blob, srcpath, treecfg):
  if srcpath not in htmlifier_store:
    htmlifier_store[srcpath] = CxxHtmlifier(blob, srcpath, treecfg)
  return htmlifier_store[srcpath].getSyntaxRegions()
htmlifier_store = {}

htmlifier = {}
for f in ('.c', '.cc', '.cpp', '.h', '.hpp'):
  htmlifier[f] = {'get_sidebar_links': get_sidebar_links,
      'get_link_regions': get_link_regions,
      'get_line_annotations': get_line_annotations,
      'get_syntax_regions': get_syntax_regions}

def get_htmlifiers():
  return htmlifier

__all__ = dxr.plugins.required_exports()
