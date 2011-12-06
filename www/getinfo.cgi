#!/usr/bin/env python2

import json
import cgitb; cgitb.enable()
import cgi
import sqlite3
import ConfigParser
import os
import sys

def locUrl(loc):
  path, line = loc.split(':')[:2]
  return '%s/%s/%s.html#l%s' % (virtroot, tree, path, line)

def getDeclarations(defid):
  cur = conn.execute("SELECT declloc FROM decldef WHERE defid=?",(defid,))
  decls = []
  for declloc, in cur:
    decls.append({ "label": "Declared at %s" % (declloc),
      "icon": "icon-decl",
      "url": locUrl(declloc)
    })
  return decls

def getType(typeinfo, refs=[], deep=False):
  if isinstance(typeinfo, int):
    typeinfo = conn.execute("SELECT * FROM types WHERE tid=?",
      (typeinfo,)).fetchone()
  typebase = {
    "label": '%s %s' % (typeinfo['tkind'], typeinfo['tqualname']),
    "icon": "icon-type",
    "children": [{
      "label": 'Definition at %s' % (typeinfo['tloc']),
      "icon": "icon-def",
      "url": locUrl(typeinfo['tloc'])
    }]
  }
  for typedef in conn.execute("SELECT * FROM typedefs WHERE tid=?",
      (typeinfo['tid'],)):
    typebase['children'].append({
      "label": 'Real value %s' % (typedef['ttypedef']),
      'icon': 'icon-def'
    })
  typebase['children'].extend(getDeclarations(typeinfo['tid']))
  if not deep:
    return typebase
  members = {
    "label": "Members",
    "icon": "icon-member",
    "children": []
  }
  tid = typeinfo['tid']
  cur = conn.cursor()
  cur.execute("SELECT tid, 't' FROM types WHERE scopeid=? UNION " +
    "SELECT funcid, 'f' FROM functions WHERE scopeid=? UNION " +
    "SELECT varid, 'v' FROM variables WHERE scopeid=?", (tid,tid,tid))
  for memid, qual in cur:
    if qual == 't':
      member = getType(memid)
    elif qual == 'f':
      member = getFunction(memid)
    elif qual == 'v':
      member = getVariable(memid)
    members["children"].append(member)
  if len(members["children"]) > 0:
    typebase["children"].append(members)

  basenode = {
    "label": "Bases",
    "icon": "icon-base",
    "children": []
  }
  derivednode = {
    "label": "Derived",
    "icon": "icon-base",
    "children": []
  }
  cur.execute("SELECT * FROM impl WHERE tbase=?", (tid,))
  for derived in cur:
    sub = getType(derived['tderived'])
    sub['label'] = '%s %s' % (sub['label'],
      derived['inhtype'] is None and "(indirect)" or "")
    derivednode["children"].append(sub)
  cur.execute("SELECT * FROM impl WHERE tderived=?", (tid,))
  for base in cur:
    sub = getType(base['tbase'])
    sub['label'] = '%s %s' % (sub['label'],
      base['inhtype'] is None and "(indirect)" or base['inhtype'])
    basenode["children"].append(sub)

  if len(basenode["children"]) > 0:
    typebase["children"].append(basenode)
  if len(derivednode["children"]) > 0:
    typebase["children"].append(derivednode)
  
  refnode = {
    "label": "References",
    "children": []
  }
  for ref in refs:
    refnode['children'].append({
      "label": ref["refloc"],
      "icon": "icon-def",
      "url": locUrl(ref["refloc"])
    })
  if len(refnode['children']) > 0:
    typebase['children'].append(refnode)
  return typebase

def getVariable(varinfo, refs=[]):
  if isinstance(varinfo, int):
    varinfo = conn.execute("SELECT * FROM variables WHERE varid=?",
      (varinfo,)).fetchone()
  varbase = {
    "label": '%s %s' % (varinfo['vtype'], varinfo['vname']),
    "icon": "icon-member",
    "children": [{
      "label": 'Definition at %s' % (varinfo['vloc']),
      "icon": "icon-def",
      "url": locUrl(varinfo['vloc'])
    }]
  }
  varbase['children'].extend(getDeclarations(varinfo['varid']))
  refnode = {
    "label": "References",
    "children": []
  }
  for ref in refs:
    refnode['children'].append({
      "label": ref["refloc"],
      "icon": "icon-def",
      "url": locUrl(ref["refloc"])
    })
  if len(refnode['children']) > 0:
    varbase['children'].append(refnode)
  return varbase

def getCallee(targetid):
  cur = conn.cursor()
  cur.execute("SELECT * FROM functions WHERE funcid=?", (targetid,))
  if cur.rowcount > 0:
    return getFunction(cur.fetchone())
  cur.execute("SELECT * FROM variables WHERE varid=?", (targetid,))
  if cur.rowcount > 0:
    return getVariable(cur.fetchone())
  cur.execute("SELECT funcid FROM targets WHERE targetid=?", (targetid,))
  refnode = { "label": "Dynamic call", "children": [] }
  for row in cur:
    refnode['children'].append(getFunction(row[0]))
  return refnode

def getFunction(funcinfo, refs=[], useCallgraph=False):
  if isinstance(funcinfo, int):
    funcinfo = conn.execute("SELECT * FROM functions WHERE funcid=?",
      (funcinfo,)).fetchone()
  funcbase = {
    "label": '%s %s%s' % (funcinfo['ftype'], funcinfo['fqualname'], funcinfo['fargs']),
    "icon": "icon-member",
    "children": [{
      "label": 'Definition at %s' % (funcinfo['floc']),
      "icon": "icon-def",
      "url": locUrl(funcinfo['floc'])
    }]
  }
  # Reimplementations
  for row in conn.execute("SELECT * FROM functions LEFT JOIN targets ON " +
      "targets.funcid = functions.funcid WHERE targetid=? AND " +
      "targets.funcid != ?",
      (-funcinfo['funcid'], funcinfo['funcid'])):
    funcbase['children'].append({
      "label": 'Reimplemented by %s%s at %s' % (row['fqualname'], row['fargs'],
        row['floc']),
      "icon": "icon-def",
      "url": locUrl(row['floc'])
    })
  funcbase['children'].extend(getDeclarations(funcinfo['funcid']))


  # References
  refnode = {
    "label": "References",
    "children": []
  }
  for ref in refs:
    refnode['children'].append({
      "label": ref["refloc"],
      "icon": "icon-def",
      "url": locUrl(ref["refloc"])
    })
  if len(refnode['children']) > 0:
    funcbase['children'].append(refnode)

  # Callgraph
  if useCallgraph:
    caller = { "label": "Calls", "children": [] }
    callee = { "label": "Called by", "children": [] }
    # This means that we want to display callee/caller information
    for info in conn.execute("SELECT callerid FROM callers WHERE targetid=? " +
        "UNION SELECT callerid FROM callers LEFT JOIN targets " +
        "ON (callers.targetid = targets.targetid) WHERE funcid=?",
        (funcinfo['funcid'], funcinfo['funcid'])):
      callee['children'].append(getFunction(info[0]))
    for info in conn.execute("SELECT targetid FROM callers WHERE callerid=?",
        (funcinfo['funcid'],)):
      caller['children'].append(getCallee(info[0]))
    if len(caller['children']) > 0:
      funcbase['children'].append(caller)
    if len(callee['children']) > 0:
      funcbase['children'].append(callee)
  return funcbase

def printError(msg='Unknown error'):
  print 'Content-Type: text/html\n\n<div class="info">%s</div>' % msg

def printMacro():
  value = conn.execute('select * from macros where macroid=?;', (refid,)).fetchone()
  macrotext = value['macrotext'] and value['macrotext'] or ''
  macroargs = value['macroargs'] and value['macroargs'] or ''
  print """Content-Type: text/html

<div class="info">
<div>%s%s</div>
<pre style="margin-top:5px">
%s
</pre>
</div>
""" % (value['macroname'], macroargs, cgi.escape(macrotext))

def printType():
  row = conn.execute("SELECT * FROM types WHERE tid=?", (refid,)).fetchone()
  refs = conn.execute("SELECT * FROM refs WHERE refid=?", (refid,))
  printTree(json.dumps(getType(row, refs, True)))

def printVariable():
  row = conn.execute("SELECT * FROM variables WHERE varid=?",
    (refid,)).fetchone()
  refs = conn.execute("SELECT * FROM refs WHERE refid=?",(refid,))
  printTree(json.dumps(getVariable(row, refs)))

def printFunction():
  row = conn.execute("SELECT * FROM functions" +
    " WHERE funcid=?", (refid,)).fetchone()
  refs = conn.execute("SELECT * FROM refs WHERE refid=?",(refid,))
  printTree(json.dumps(getFunction(row, refs, True)))

def printReference():
  val = conn.execute("SELECT 'var' FROM variables WHERE varid=?" +
    " UNION SELECT 'func' FROM functions WHERE funcid=?" +
    " UNION SELECT 't' FROM types WHERE tid=?" +
    " UNION SELECT 'm' FROM macros WHERE macroid=?",
    (refid,refid,refid,refid)).fetchone()[0]
  return dispatch[val]()

def printTree(jsonString):
  print """Content-Type: application/json

%s
""" % (jsonString)


form = cgi.FieldStorage()

type = ''
tree = ''
virtroot = ''

if form.has_key('type'):
  type = form['type'].value

if form.has_key('tree'):
  tree = form['tree'].value

if form.has_key('virtroot'):
  virtroot = form['virtroot'].value

if form.has_key('rid'):
  refid = form['rid'].value

try:
  config = ConfigParser.ConfigParser()
  config.read(['/etc/dxr/dxr.config', os.getcwd() + '/dxr.config'])
  wwwdir = config.get('Web', 'wwwdir')
except:
  msg = sys.exc_info()[1] # Python 2/3 compatibility
  printError('Error loading dxr.config: %s' % msg)
  sys.exit(0)

dxrdb = os.path.join(wwwdir, tree, '.dxr_xref', tree  + '.sqlite');
conn = sqlite3.connect(dxrdb)
conn.execute('PRAGMA temp_store = MEMORY;')
conn.row_factory = sqlite3.Row

dispatch = {
    'var': printVariable,
    'func': printFunction,
    't': printType,
    'm': printMacro,
    'ref': printReference,
}
dispatch.get(type, printError)()
