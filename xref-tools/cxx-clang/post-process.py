#!/usr/bin/python

import csv

class UnionFind:
  class _Obj:
    def __init__(self, val):
      self.val = val
      self.rank = 0
      self.parent = self

  def __init__(self):
    self.objects = {}

  def _canonicalize(self, obj):
    if obj in self.objects:
      return self.objects[obj]
    canon = _Obj(obj)
    self.objects[obj] = canon
    return canon

  def find(self, obj):
    return self._find(self._canonicalize(obj)).obj

  def _find(self, canon):
    if canon.parent != canon:
      canon.parent = self.find(canon.parent)
    return canon

  def union(self, obj1, obj2):
    obj1 = self._canonicalize(obj1)
    obj2 = self._canonicalize(obj2)
    x, y = self._find(obj1), self._find(obj2)
    if x == y:
      return

    if x.rank < y.rank:
      x.parent = y
    elif x.rank > y.rank:
      y.parent = x
    else:
      y.parent = x
      x.rank += 1

  def set(self, obj, newval):
    canon = self._find(obj)
    canon.obj = newval
    if newval not in self.objects:
      self.objects[newval] = canon

decl_master = {}
types = {}
typedefs = {}
functions = {}
inheritance = set()
variables = {}
refs = []

def process_decldef(args):
  name, defloc, declloc = args['name'], args['defloc'], args['declloc']
  decl_master[(name, declloc)] = defloc
  decl_master[(name, defloc)] = defloc

def process_type(typeinfo):
  types[(typeinfo['tname'], typeinfo['tloc'])] = typeinfo

def process_typedef(typeinfo):
  typedefs[(typeinfo['tname'], typeinfo['tloc'])] = typeinfo

def process_function(funcinfo):
  functions[(funcinfo['flongname'], funcinfo['floc'])] = funcinfo

def process_impl(info):
  inheritance.add(info)

def process_variable(varinfo):
  variables[varinfo['vname'], varinfo['vloc']] = varinfo

def process_ref(info):
  refs.append(info)

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
  finally:
    f.close()

files = []
def collect_files(arg, dirname, fnames):
  for name in fnames:
    if os.path.isdir(name): continue
    if not name.endswith(arg): continue
    files.append(os.path.join(dirname, name))

def produce_sql(sqlout):
  def canonicalize_decl(name, loc):
    return (name, decl_master.get((name, loc), loc))

  # Produce all scopes
  scopes = {}
  nextIndex = 1
  typeKeys = set()
  for t in types:
    key = canonicalize_decl(t[0], t[1])
    if key not in scopes:
      typeKeys.add(key)
      scopes[key] = nextIndex
      nextIndex += 1
  funcKeys = set()
  for f in functions:
    key = canonicalize_decl(f[0], f[1])
    if key not in scopes:
      funcKeys.add(key)
      scopes[key] = nextIndex
      nextIndex += 1

  # Variables aren't scoped, but we still need to refer to them in the same
  # manner, so we'll unify variables with the scope ids
  varKeys = {}
  for v in variables:
    key = (v[0], v[1])
    if key not in varKeys:
      varKeys[key] = nextIndex
      nextIndex += 1

  # Scopes are now defined, this allows us to modify structures for sql prep

  # Inheritance:
  # We need to canonicalize the types and then set up the inheritance tree
  # Since we don't know which order we'll see the pairs, we have to propagate
  # bidirectionally when we find out more.
  def build_inherits(base, child, direct):
    return {
        'tbname': base[0], 'tbloc': base[1],
        'tcname': child[0], 'tcloc': child[1],
        'direct': direct}
  childMap, parentMap = {}, {}
  inheritsTree = []
  for info in inheritance:
    base = canonicalize_decl(info['tbname'], info['tbloc'])
    child = canonicalize_decl(info['tcname'], info['tcloc'])
    subs = childMap.setdefault(base, set())
    supers = parentMap.setdefault(child, set())
    inheritsTree.append(build_inherits(base, child, True))
    inheritsTree.extend([build_inherits(base, sub, False) for sub in subs])
    inheritsTree.extend([build_inherits(sup, child, False) for sup in supers])
    subs.append(child)
    supers.append(base)

  # Fix up (name, loc) pairs to ids
  for fkey in funcKeys:
    funcinfo = functions[fkey]
    if 'scopename' in funcinfo:
      funcinfo['scopeid'] = scopes[canonize_decl(funcinfo.pop('scopename'),
        funcinfo.pop('scopeloc'))]
    else:
      funcinfo['scopeid'] = 0

  for vkey in varKeys:
    varinfo = variables[vkey]
    if 'scopename' in varinfo:
      varinfo['scopeid'] = scopes[canonicalize_decl(varinfo.pop('scopename'),
        varinfo.pop('scopeloc'))]
    else:
      varinfo['scopeid'] = 0
  
  varRefs = []
  for ref in refs:
    canon = canonicalize_decl(ref.pop('varname'), ref.pop('varloc'))
    if canon in varKeys:
      ref['varid'] = varKeys[canon]
      varRefs.append(ref)

  # Finally, produce all sql statements
  def write_sql(table, obj):
    keys, vals = zip(*obj.iteritems())
    sqlout.write("INSERT INTO " + table + " (" + ','.join(keys) + ") VALUES" +
      " (" + ",".join([repr(v) for v in vals]) + ");\n");
  for s in scopes:
    write_sql("scopes", {"scopeid": scopes[s], "sname": s[0], "sloc": s[1]})
  for f in funcKeys:
    write_sql("functions", functions[f])
  for v in varKeys:
    write_sql("variables", variables[v])
  for t in typeKeys:
    write_sql("types", types[t])
  for t in typedefs:
    write_sql("types", typedefs[t])
  for i in inheritsTree:
    write_sql("impl", i)
  for r in varRefs:
    write_sql("variable_refs", varRefs[r])

# Run this on the srcdir
import sys, os

os.path.walk(sys.argv[1], collect_files, ".csv")
for f in files:
  load_indexer_output(f)
produce_sql(sys.stdout)
