#!/usr/bin/env python

import cgitb; cgitb.enable()
import cgi
import sqlite3
import ConfigParser
import os

form = cgi.FieldStorage()

name = ''
type = ''
file = ''
line = ''
tree = ''
virtroot = ''

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

config = ConfigParser.ConfigParser()
config.read('dxr.config')

dxrdb = os.path.join(config.get('Web', 'wwwdir'), tree, '.dxr_xref', tree  + '.sqlite');
htmlsrcdir = os.path.join(virtroot, tree) + '/'

conn = sqlite3.connect(dxrdb)
conn.execute('PRAGMA temp_store = MEMORY;')

data = ''
members = ''
bases = ''
concrete = ''

print 'Content-Type: text/html\n'
print """<div id="titlebar" class="titlebar"><div class="close" onClick="dijit.byId('ttd').onCancel();">&nbsp;</div></div>
<div dojoType="dijit.layout.TabContainer" style="width: 500px; height: 300px;">
"""  

def PrintStatement():
  # TODO: deal with this matching multiple in same line...
  row = conn.execute('select vname, vtype, vdeclloc, visFcall, vmember from stmts where vlocf=? and vlocl=? and vshortname=?;', (file, line, name)).fetchone()

  data = None

  if not row:
    data += "Error: Couldn't find " + name + " at line " + line + " as expected."
  else:
    includeType = False
    data = "Name: " + row[0]
    if row[1]:
      data += "<br />Type: " + row[1]
    if row[2] and row[2] != 'should not happen!':
      parts = row[2].split(':')
      data += '<br />Declaration: <a href="' + htmlsrcdir + parts[0] + '.html#l' + parts[1] + '">' + row[2] + '</a>'
      includeType = True
      print """
<div dojoType="dijit.layout.ContentPane" title="Statement">
<p>
%s
</p>
</div>
""" % (data,)
  
    impl_data = ''

    # If this is a function call, do more work to get extra info
    if row[3] and row[3] == 1:
      impl_data = '<ul>'
      for impl in conn.execute('select mtname, mname, mdecl, mdef from members where mname=? and mtname in (select tcname from impl where tbname=?);', (row[0], row[4])):
        pathParts = ''
        if impl[3]:
          pathParts = impl[3].split(':')
        else:
          pathParts = impl[2].split(':')
        impl_data += '<li><a href="' + htmlsrcdir + pathParts[0] + ".html#l" + pathParts[1] + '">' + impl[0] + "::" + impl[1] + "</a></li>"
      impl_data += "</ul>"

    if impl_data != '<ul></ul>' and impl_data != '':
      print """
<div dojoType="dijit.layout.ContentPane" title="Implementations">
<p>
%s
</p>
</div>
""" % (impl_data,)
  
    if includeType:
      # drop * from nsIFoo* in cases where we've added
      PrintType(row[1].replace('*', ''))

    users_data = ''
    # Get other users of this same statement
    if row[2]:
      users_data = '<ul>'
      for user in conn.execute('select vlocf, vlocl from stmts where vname=? and vtype=? and vdeclloc=?;', (row[0], row[1], row[2])):
        # Don't include decl itself
        loc = user[0] + ':' + str(user[1])
        if row[2] != loc:
          users_data += '<li><a href="' + htmlsrcdir + user[0] + ".html#l" + str(user[1]) + '">' + user[0] + ":" + str(user[1]) + "</a></li>"
      users_data += "</ul>"

#    if users_data != '<ul></ul>' and users_data != '':
    print """
<div dojoType="dijit.layout.ContentPane" title="Users">
<p>
%s
</p>
</div>
""" % (users_data,)


def PrintMember():
  # XXX: this will catch wrong ones...
  row = conn.execute('select mname, mdecl, mtname, mtloc from members where mshortname=?', (name, )).fetchone()
  mname = row[0]
  mdecl = row[1]
  mdeclParts = mdecl.split(':')
  mtname = row[2]
  mtloc = row[3]
  mtlocParts = mtloc.split(':')

  member_data = 'Member: <a href="' + htmlsrcdir + mtlocParts[0] + '.html#l' + mtlocParts[1] + '">' + mtname + '</a>::'
  member_data += '<a href="' + htmlsrcdir + mdeclParts[0] + '.html#l' + mdeclParts[1] + '">' + mname + '</a>'
  
  print """
<div dojoType="dijit.layout.ContentPane" title="Member Info">
<p>
%s
</p>
</div>
""" % (member_data,)


def PrintMacro():
    value = conn.execute('select mname, mvalue from macros where mshortname=?;', (name,)).fetchone()
    print """
<div dojoType="dijit.layout.ContentPane" title="Macro">
<pre>
%s<br />
%s
</pre>
</div>
""" % (value[0], cgi.escape(value[1]))


def PrintType(typename):
  if typename == '':
    return

#  row = conn.execute('select tname, ttypedefname, ttypedefloc, tkind, ttemplate, tloc from types where tname=? or ttemplate=? or ttypedefname=?;', (typename,typename,typename)).fetchone()
  row = conn.execute('select tname, ttypedefname, ttypedefloc, tkind, ttemplate, tloc from types where tname=?;', (typename,)).fetchone()

  # see if we got a match, otherwise it's a template name
  if not row:
    row = conn.execute('select tname, ttypedefname, ttypedefloc, tkind, ttemplate, tloc from types where ttemplate=?;', (typename,)).fetchone()

  tname = row[0]
  ttypedefname = row[1] or ''
  ttypedefloc = row[2] or ''
  tkind = row[3]
  ttemplate = row[4] or ''
  tloc = row[5]
  tlocParts = tloc.split(':')

  data =  "Type: " + tname + " (" + tkind + ")<br />"
  data += 'Declaration: <a href="' + htmlsrcdir + tlocParts[0] + '.html#l' + tlocParts[1] + '">' + tloc + '</a><br />'

  if ttypedefname:
    data += "Typdef Type: " + ttypedefname + "<br />"
  if ttemplate:
    data += "Template Type: " + ttemplate + "<br />"

  members = "<ul>"
  # TODO: should add mdef in here somehow...
  for member in conn.execute('select mname, mdecl, mvalue from members where mtname=? and mtloc=?;', (typename, tloc)):
    mname = member[0]
    mdecl = member[1]
    mdeclParts = mdecl.split(':')
    mvalue = member[2] or ''

    members += "<li>"
    if mvalue:
      members += '<a href="' + htmlsrcdir + mdeclParts[0] + '.html#l' + mdeclParts[1] + '">' + mname + '</a> (Value = ' + mvalue + ")"
    else:
      members += '<a href="' + htmlsrcdir + mdeclParts[0] + '.html#l' + mdeclParts[1] + '">' + mname + '</a>'
    members += "</li>"
  members += "</ul>"

  bases = 'Direct:<br /><ul>'
  for base in conn.execute('select tbname, tbloc from impl where tcname=? and tcloc=? and direct=1;', (typename, tloc)):
    tblocParts = base[1].split(':')
    bases += '<li><a href="' + htmlsrcdir + tblocParts[0] + '.html#l' + tblocParts[1] + '">' + base[0] + '</a></li>' 
  bases += '</ul>'
  bases += 'Indirect:<br /><ul>'
  for base in conn.execute('select tbname, tbloc from impl where tcname=? and tcloc=? and not direct=1;', (typename, tloc)):
    tblocParts = base[1].split(':')
    bases += '<li><a href="' + htmlsrcdir + tblocParts[0] + '.html#l' + tblocParts[1] + '">' + base[0] + '</a></li>' 
  bases += '</ul>'

  concrete = 'Direct:<br /><ul>'
  for child in conn.execute('select tcname, tcloc from impl where tbname=? and tbloc=? and direct=1;', (typename, tloc)):
    tclocParts = child[1].split(':')
    concrete += '<li><a href="' + htmlsrcdir + tclocParts[0] + '.html#l' + tclocParts[1] + '">' + child[0] + '</a></li>' 
  concrete += '</ul>'
  concrete += 'Indirect:<br /><ul>'
  for child in conn.execute('select tcname, tcloc from impl where tbname=? and tbloc=? and not direct=1;', (typename, tloc)):
    tclocParts = child[1].split(':')
    concrete += '<li><a href="' + htmlsrcdir + tclocParts[0] + '.html#l' + tclocParts[1] + '">' + child[0] + '</a></li>' 
  concrete += '</ul>'

  print """
<div dojoType="dijit.layout.ContentPane" title="Type Info">
<p>
%s
</p>
</div>
""" % (data,)

  if members != '<ul></ul>':
    print """
<div dojoType="dijit.layout.ContentPane" title="Members">
<p>
%s
</p>
</div>
""" % (members,)

  if bases != 'Direct:<br /><ul></ul>Indirect:<br /><ul></ul>':
    print """
<div dojoType="dijit.layout.ContentPane" title="Bases">
<p>
%s
</p>
</div>
""" % (bases,)

  if concrete != 'Direct:<br /><ul></ul>Indirect:<br /><ul></ul>':
    print """
<div dojoType="dijit.layout.ContentPane" title="Derived">
<p>
%s
</p>
</div>
""" % (concrete,)


if type == 's' or type == 's-fuzzy':
  PrintStatement()

if type == 'mem':    # member
  PrintMember()

if type == 't':    # type
  PrintType(name)

if type == 'm':    # macro
  PrintMacro()
    
# close main div
print "</div>"
