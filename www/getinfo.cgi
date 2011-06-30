#!/usr/bin/env python2.6

import json
import cgitb; cgitb.enable()
import cgi
import sqlite3
import ConfigParser
import os

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
  if len(members) > 0:
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

def getFunction(funcinfo, refs=[]):
  if isinstance(funcinfo, int):
    funcinfo = conn.execute("SELECT * FROM functions WHERE funcid=?",
      (funcinfo,)).fetchone()
  funcbase = {
    "label": funcinfo['flongname'],
    "icon": "icon-member",
    "children": [{
      "label": 'Definition at %s' % (funcinfo['floc']),
      "icon": "icon-def",
      "url": locUrl(funcinfo['floc'])
    }]
  }
  funcbase['children'].extend(getDeclarations(funcinfo['funcid']))
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
  return funcbase

def printError():
  print """Content-Type: text/html

<div class="info">Um, this isn't right...</div>"""

def printMacro():
  value = conn.execute('select mname, mvalue from macros where mshortname=?;', (name,)).fetchone()
  print """Content-Type: text/html

<div class="info">
<div>%s</div>
<pre style="margin-top:5px">
%s
</pre>
</div>
""" % (value[0], cgi.escape(value[1]))

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
  row = conn.execute("SELECT fname, floc, flongname FROM functions" +
    " WHERE funcid=?", (refid,)).fetchone()
  refs = conn.execute("SELECT * FROM refs WHERE refid=?",(refid,))
  printTree(json.dumps(getFunction(row, refs)))

def printReference():
  val = conn.execute("SELECT 'var' FROM variables WHERE varid=?" +
    " UNION SELECT 'func' FROM functions WHERE funcid=?" +
    " UNION SELECT 't' FROM types WHERE tid=?",
    (refid,refid,refid)).fetchone()[0]
  return dispatch[val]()

def printTree(jsonString):
  print """Content-Type: text/html

<script type="text/javascript">
  dojo.addOnLoad(function() {
    buildTree(%s, "tree-%s");
  });
</script>
<div class="info">
<div id="tree-%s" style="margin:0"></div>
</div>
""" % (jsonString, div, div)


form = cgi.FieldStorage()

name = ''
type = ''
file = ''
line = ''
tree = ''
virtroot = ''
div = ''

if form.has_key('name'):
  name = form['name'].value

if form.has_key('type'):
  type = form['type'].value

if form.has_key('line'):
  line = form['line'].value

if form.has_key('file'):
  file = form['file'].value

if form.has_key('tree'):
  tree = form['tree'].value

if form.has_key('virtroot'):
  virtroot = form['virtroot'].value

if form.has_key('div'):
  div = form['div'].value

if form.has_key('rid'):
  refid = form['rid'].value

config = ConfigParser.ConfigParser()
config.read('dxr.config')

dxrdb = os.path.join(config.get('Web', 'wwwdir'), tree, '.dxr_xref', tree  + '.sqlite');
htmlsrcdir = os.path.join('/', virtroot, tree) + '/'

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
