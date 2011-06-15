#!/usr/bin/python

import csv
import os
import sys

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
references = {}

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
  functions[(funcinfo['flongname'], funcinfo['floc'])] = funcinfo

def process_impl(info):
  inheritance.add(info)

def process_variable(varinfo):
  variables[varinfo['vname'], varinfo['vloc']] = varinfo

def process_ref(info):
  # Each reference is pretty much unique, but we might record it several times
  # due to header files.
  references[info['varname'], info['varloc'], info['refloc']] = info

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

file_names = []
def collect_files(arg, dirname, fnames):
  for name in fnames:
    if os.path.isdir(name): continue
    if not name.endswith(arg): continue
    file_names.append(os.path.join(dirname, name))

def make_blob():
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
      types[key]['tid'] = scopes[key] = nextIndex
      nextIndex += 1
  # Typedefs need a tid, but they are not a scope
  for t in typedefs:
    typedefs[t]['tid'] = nextIndex
    nextIndex += 1
  funcKeys = set()
  for f in functions:
    key = canonicalize_decl(f[0], f[1])
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
      ref['refid'] = functions[canon]['scopeid']
      refs.append(ref)

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
  return blob

def post_process(srcdir, objdir):
  os.path.walk(srcdir, collect_files, ".csv")
  for f in file_names:
    load_indexer_output(f)
  blob = make_blob()
  
  # Reindex everything by file
  def schema():
    return { "scopes": [], "functions": [], "variables": [], "types": [],
      "refs": [] }
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

  # Normalize path names
  blob["byfile"] = {}
  for f in files:
    real = os.path.relpath(os.path.realpath(os.path.join(srcdir, f)), srcdir)
    realtbl = blob["byfile"].setdefault(real, schema())
    oldtbl = files[f]
    for table in oldtbl:
      realtbl[table].extend(oldtbl[table])
  return blob

def sqlify(blob):
  out = [];
  # Finally, produce all sql statements
  def write_sql(table, obj, out):
    keys, vals = zip(*obj.iteritems())
    out.append("INSERT INTO " + table + " (" + ','.join(keys) + ") VALUES" + 
      " (" + ",".join([repr(v) for v in vals]) + ");")
  for table in blob:
    if table == "byfile": continue
    iskey = isinstance(blob[table], dict)
    for row in blob[table]:
      if iskey:
        row = blob[table][row]
      write_sql(table, row, out)
  return '\n'.join(out)

__all__ = ['post_process', 'sqlify']

if __name__ == '__main__':
  sys.stdout.write(sqlify(post_process(sys.argv[1], sys.argv[1])))
