#!/usr/bin/env python2.6

import dxr_data
import json
import cgitb; cgitb.enable()
import cgi
import sqlite3
import ConfigParser
import os

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
  t = dxr_data.DxrType.find(name, conn)
  jsonString = json.dumps(t, cls=dxr_data.DxrType.DojoEncoder)
  printTree(jsonString)

def printVariable():
  row = conn.execute("SELECT vname, vloc FROM variables WHERE varid=?",
    (refid,)).fetchall()[0]
  s = dxr_data.DxrMember(row[0], row[0], None, row[1], None, conn)
  jsonString = json.dumps(s, cls=dxr_data.DxrStatement.DojoEncoder)
  printTree(jsonString)

def printFunction():
  row = conn.execute("SELECT fname, floc, flongname FROM functions" +
    " WHERE funcid=?", (refid,)).fetchall()[0]
  s = dxr_data.DxrMember(row[2], row[0], None, row[1], None, conn)
  jsonString = json.dumps(s, cls=dxr_data.DxrStatement.DojoEncoder)
  printTree(jsonString)

def printReference():
  val = conn.execute("SELECT 'var' FROM variables WHERE varid=?" +
    " UNION SELECT 'func' FROM functions WHERE funcid=?" +
    " UNION SELECT 't' FROM types WHERE tid=?",
    (refid,refid,refid)).fetchall()[0][0]
  return dispatch[val]()
# TODO - gotta get this stuff added somehow and deal with functions...
#    # If this is a function call, do more work to get extra info
#    if row[3] and row[3] == 1:
#      impl_data = '<ul>'
##      for impl in conn.execute('select mtname, mname, mdecl, mdef from members where mname=? and mtname in (select tcname from impl where tbname=?);', (row[0], row[4])):
#      for impl in conn.execute('select mtname, mname, mdecl, mdef, mtloc from members where mname=? and (mtname=? or (not mtname=? and mtname in (select tcname from impl where tbname=?)));', (row[0], row[4], row[4], row[4])):
#        # Skip IDL interface types, which provide no implementation
#        mtype = conn.execute('select tkind from types where tname=? and tloc=?;', (impl[0], impl[4])).fetchone()
#        if mtype and mtype[0] == 'interface':
#          continue
#        pathParts = ''
#        if impl[3]:
#          pathParts = impl[3].split(':')
#        else:
#          pathParts = impl[2].split(':')
#        impl_data += '<li><a href="' + htmlsrcdir + pathParts[0] + ".html#l" + pathParts[1] + '">' + impl[0] + "::" + impl[1] + "</a></li>"
#      impl_data += "</ul>"
#
#    if impl_data != '<ul></ul>' and impl_data != '':
#      print """
#<div dojoType="dijit.layout.ContentPane" title="Implementations">
#<p>
#%s
#</p>
#</div>
#""" % (impl_data,)
#  
#    if includeType:
#      # drop * from nsIFoo* in cases where we've added
#      PrintType(row[1].replace('*', ''))
#
#    users_data = ''
#    # Get other users of this same statement
#    if row[2]:
#      users_data = '<ul>'
#      for user in conn.execute('select vlocf, vlocl from stmts where vname=? and vtype=? and vdeclloc=?;', (row[0], row[1], row[2])):
#        # Don't include decl itself
#        loc = user[0] + ':' + str(user[1])
#        if row[2] != loc:
#          users_data += '<li><a href="' + htmlsrcdir + user[0] + ".html#l" + str(user[1]) + '">' + user[0] + ":" + str(user[1]) + "</a></li>"
#      users_data += "</ul>"
#
##    if users_data != '<ul></ul>' and users_data != '':
#    print """
#<div dojoType="dijit.layout.ContentPane" title="Users">
#<p>
#%s
#</p>
#</div>
#""" % (users_data,)

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

dispatch = {
    'var': printVariable,
    'func': printFunction,
    't': printType,
    'm': printMacro,
    'ref': printReference,
}
dispatch.get(type, printError)()
