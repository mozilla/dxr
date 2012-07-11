#!/usr/bin/env python

import json
import cgitb; cgitb.enable()
import cgi
import sqlite3
import os
import sys
import re
import dxr_server

def locUrl(path, line):
  return '%s/%s/%s.html#l%s' % (virtroot, tree, path, line)

def getDeclarations(defid):
  row = conn.execute("SELECT (SELECT path FROM files WHERE files.ID=decldef.file_id) AS file_path, file_line, file_col FROM decldef WHERE defid=?",(defid,)).fetchone()

  if row is None:
    row = conn.execute("SELECT (SELECT path FROM files WHERE files.ID = functions.file_id) AS file_path, file_line, file_col FROM functions where funcid = ?", (defid,)).fetchone()

  if row is None:
    return {}

  decls = []
  declpath, declline, declcol = row
  decls.append({ "label": "Declared at %s:%d:%d" % (declpath, declline, declcol),
    "icon": "icon-decl",
    "url": locUrl(declpath, declline)
  })
  return decls

def getType(typeinfo, refs=[], deep=False):
  typedef = None

  if isinstance(typeinfo, int):
    typeinfo = conn.execute("SELECT *, (SELECT path FROM files WHERE files.ID=types.file_id) AS file_path FROM types WHERE tid=?",
      (typeinfo,)).fetchone()

  try:
    label = '%s %s' % (typeinfo['tkind'], typeinfo['tqualname'])
  except:
    typedef = typeinfo['ttypedef']
    label = 'Typedef to %s' % (typedef,)
    pass

  typebase = {
    "label": label,
    "icon": "icon-type",
    "children": [{
      "label": 'Definition at %s:%d:%d' % (typeinfo['file_path'], typeinfo['file_line'], typeinfo['file_col']),
      "icon": "icon-def",
      "url": locUrl(typeinfo['file_path'], typeinfo['file_line'])
    }]
  }

  if typedef is not None:
    words = typedef.split(' ', 2)
    row = conn.execute ("""SELECT *, (SELECT path FROM files WHERE files.ID=decldef.definition_file_id)
                           AS file_path FROM decldef WHERE defid IN (SELECT tid FROM types WHERE tkind=? AND tname=?)""",
                        (words[0], words[1])).fetchone()

    if row is not None:
      typebase['children'].append({
        "label": "Real value defined at %s:%d:%d" % (row['file_path'], row['definition_file_line'], row['definition_file_col']),
        "icon": 'icon-def',
        "url": locUrl(row['file_path'], row['definition_file_line'])
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
      "label": "%s:%d:%d" % (ref["file_path"], ref["file_line"], ref["file_col"]),
      "icon": "icon-def",
      "url": locUrl(ref["file_path"], ref["file_line"])
    })
  if len(refnode['children']) > 0:
    typebase['children'].append(refnode)
  return typebase

def getVariable(varinfo, refs=[]):
  if isinstance(varinfo, int):
    varinfo = conn.execute("SELECT *, (SELECT path FROM files WHERE files.ID=variables.file_id) AS file_path FROM variables WHERE varid=?",
      (varinfo,)).fetchone()
  varbase = {
    "label": '%s %s' % (varinfo['vtype'], varinfo['vname']),
    "icon": "icon-member",
    "children": [{
      "label": 'Definition at %s:%d:%d' % (varinfo['file_path'], varinfo['file_line'], varinfo['file_col']),
      "icon": "icon-def",
      "url": locUrl(varinfo['file_path'], varinfo['file_line'])
    }]
  }
  varbase['children'].extend(getDeclarations(varinfo['varid']))
  refnode = {
    "label": "References",
    "children": []
  }
  for ref in refs:
    refnode['children'].append({
      "label": "%s:%d:%d" % (ref["file_path"], ref["file_line"], ref["file_col"]),
      "icon": "icon-def",
      "url": locUrl(ref["file_path"], ref["file_line"])
    })
  if len(refnode['children']) > 0:
    varbase['children'].append(refnode)
  return varbase

def getCallee(targetid):
  cur = conn.cursor()
  row = cur.execute("SELECT *, (SELECT path FROM files WHERE files.ID=functions.file_id) AS file_path FROM functions WHERE funcid=?", (targetid,)).fetchone()

  if row is not None:
    return getFunction(row)

  row = cur.execute("SELECT *, (SELECT path FROM files WHERE files.ID=variables.file_id) AS file_path FROM variables WHERE varid=?", (targetid,)).fetchone()
  if row is not None:
    return getVariable(row)
  cur.execute("SELECT funcid FROM targets WHERE targetid=?", (targetid,))
  refnode = { "label": "Dynamic call", "children": [] }
  for row in cur:
    refnode['children'].append(getFunction(row[0]))
  return refnode

def getFunction(funcinfo, refs=[], useCallgraph=False):
  if isinstance(funcinfo, int):
    defid = funcinfo
    row = conn.execute("SELECT defid FROM decldef, functions WHERE decldef.file_id = functions.file_id AND " +
                       "decldef.file_line = functions.file_line AND decldef.file_col = functions.file_col AND funcid = ?",
                       (funcinfo,)).fetchone()
    if row is not None:
      funcinfo = row[0]

    funcinfo = conn.execute("SELECT *, (SELECT path FROM files WHERE files.ID=functions.file_id) AS file_path FROM functions WHERE funcid=?",
      (funcinfo,)).fetchone()
  else:
    defid = funcinfo['funcid']
  funcbase = {
    "label": '%s %s%s' % (funcinfo['ftype'], funcinfo['fqualname'], funcinfo['fargs']),
    "icon": "icon-member",
    "children": [{
      "label": 'Definition at %s:%d:%d' % (funcinfo['file_path'], funcinfo['file_line'], funcinfo['file_col']),
      "icon": "icon-def",
      "url": locUrl(funcinfo['file_path'], funcinfo['file_line'])
    }]
  }

  # Reimplementations
  for row in conn.execute("SELECT *, (SELECT path FROM files WHERE files.ID=functions.file_id) AS file_path " +
      "FROM functions LEFT JOIN targets ON " +
      "targets.funcid = functions.funcid WHERE targetid=? AND " +
      "targets.funcid != ?",
      (-funcinfo['funcid'], funcinfo['funcid'])):
    funcbase['children'].append({
      "label": 'Reimplemented by %s%s at %s:%d:%d' % (row['fqualname'], row['fargs'],
        row['file_path'], row['file_line'], row['file_col']),
      "icon": "icon-def",
      "url": locUrl(row['file_path'], row['file_line'])
    })
  funcbase['children'].extend(getDeclarations(funcinfo['funcid']))


  # References
  refnode = {
    "label": "References",
    "children": []
  }
  for ref in refs:
    refnode['children'].append({
      "label": "%s:%d:%d" % (ref["file_path"], ref["file_line"], ref["file_col"]),
      "icon": "icon-def",
      "url": locUrl(ref["file_path"], ref["file_line"])
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
        (defid, defid)):
      callee['children'].append(getFunction(info[0]))
    for info in conn.execute("SELECT targetid FROM callers WHERE callerid=?",
         (defid,)):
      caller['children'].append(getCallee(info[0]))
    if len(caller['children']) > 0:
      funcbase['children'].append(caller)
    if len(callee['children']) > 0:
      funcbase['children'].append(callee)
  return funcbase

def printError(msg='Unknown error'):
  print 'Content-Type: text/html\n\n<div>%s</div>' % msg

def printMacro():
  value = conn.execute('select *, (select path from files where id=macros.file_id) as path from macros where macroid=?;', (refid,)).fetchone()
  macrotext = value['macrotext'] and value['macrotext'] or ''
  macroargs = value['macroargs'] and value['macroargs'] or ''
  url = locUrl(value['path'], value['file_line'])
  print """Content-Type: text/html

<div>
<div><a href="%s">%s</a>%s</div>
<pre style="margin-top:5px">
%s
</pre>
</div>
""" % (url, value['macroname'], macroargs, cgi.escape(macrotext))

def printType():
  row = conn.execute("SELECT *, (SELECT path FROM files WHERE files.ID=types.file_id) " +
                     "AS file_path FROM types WHERE tid=?", (refid,)).fetchone()
  if row is None:
    row = conn.execute ("SELECT *, (SELECT path FROM files WHERE files.ID=typedefs.file_id) " +
                        "AS file_path FROM typedefs WHERE tid=?", (refid,)).fetchone()

  refs = conn.execute("SELECT *, (SELECT path FROM files WHERE files.ID=refs.file_id) " +
                      "AS file_path FROM refs WHERE refid=?", (refid,))
  printTree(json.dumps(getType(row, refs, True)))

def printVariable():
  row = conn.execute("SELECT *, (SELECT path FROM files WHERE files.ID=variables.file_id) " +
                     "AS file_path FROM variables WHERE varid=?",
    (refid,)).fetchone()
  refs = conn.execute("SELECT *, (SELECT path FROM files WHERE files.ID=refs.file_id) " +
                      "AS file_path FROM refs WHERE refid=?", (refid,))
  printTree(json.dumps(getVariable(row, refs)))

def printFunction():
  refs = conn.execute("SELECT *, (SELECT path FROM files WHERE files.ID=refs.file_id) " +
                      "AS file_path FROM refs WHERE refid=?", (refid,))
  printTree(json.dumps(getFunction(int(refid), refs, True)))

def printReference():
  row = None
  stmt = conn.execute("SELECT 'var' FROM variables WHERE varid=?" +
                      " UNION SELECT 'func' FROM functions WHERE funcid=?" +
                      " UNION SELECT 't' FROM types WHERE tid=?" +
                      " UNION SELECT 't' FROM typedefs WHERE tid=?" +
                      " UNION SELECT 'm' FROM macros WHERE macroid=?",
                      (refid,refid,refid,refid,refid))

  if stmt is not None:
    row = stmt.fetchone()

  if row is None:
    return printError("This reference is not defined in the indexed code");

  val = row[0]
  return dispatch[val]()

def printTree(jsonString):
  print """Content-Type: application/json

%s
""" % (jsonString)


form = cgi.FieldStorage()

type = None
tree = None
virtroot = ''
refid = None
forbidden = r'[^0-9a-zA-Z-_]'

if form.has_key('type') and not re.search(forbidden, form['type'].value):
  type = form['type'].value

if form.has_key('tree') and not re.search(forbidden, form['tree'].value):
  tree = form['tree'].value

if form.has_key('rid'):
  refid = int(form['rid'].value)

if type is None or tree is None or refid is None:
  printError('Invalid parameters')
  sys.exit(0)

conn = dxr_server.connect_db(tree)

dispatch = {
    'var': printVariable,
    'func': printFunction,
    't': printType,
    'm': printMacro,
    'ref': printReference,
}
dispatch.get(type, printError)()
