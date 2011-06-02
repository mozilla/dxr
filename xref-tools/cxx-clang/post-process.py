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
functions = {}

def process_decldef(args):
  name, defloc, declloc = args['name'], args['defloc'], args['declloc']
  decl_master[(name, declloc)] = defloc
  decl_master[(name, defloc)] = defloc

def process_type(typeinfo):
  types[(typeinfo['tname'], typeinfo['tloc'])] = typeinfo

def process_function(funcinfo):
  functions[(funcinfo['flongname'], funcinfo['floc'])] = funcinfo

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

  # Scopes are now defined, this allows us to modify structures for sql prep
  for fkey in funcKeys:
    funcinfo = functions[fkey]
    if 'scopename' in funcinfo:
      funcinfo['scopeid'] = scopes[funcinfo.pop('scopename'),
        funcinfo.pop('scopeloc')]
    else:
      funcinfo = 0

  # Finally, produce all sql statements
  def write_sql(table, obj):
    keys, vals = zip(*obj.iteritems())
    sqlout.write("INSERT INTO " + table + " (" + ','.join(keys) + ") VALUES" +
      " (" + ",".join([repr(v) for v in vals]) + ");\n");
  for s in scopes:
    write_sql("scopes", {"scopeid": scopes[s], "sname": s[0], "sloc": s[1]})
  for f in funcKeys:
    write_sql("functions", functions[f])
  for t in typeKeys:
    write_sql("types", types[t])

# Run this on the srcdir
import sys, os

os.path.walk(sys.argv[1], collect_files, ".csv")
for f in files:
  load_indexer_output(f)
produce_sql(sys.stdout)
