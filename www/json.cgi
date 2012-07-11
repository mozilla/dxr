#!/usr/bin/env python2

import cgitb; cgitb.enable()
import sqlite3
import cgi
import sys
import os
import re
import ctypes

import dxr_server
from dxr_server import queries
from dxr_server import json

# Load query parameters
fieldStorage = cgi.FieldStorage()
form = dict((key, fieldStorage.getvalue(key)) for key in fieldStorage.keys())


for treecfg in dxr_server.trees:
  if 'tree' in form and treecfg != form['tree']:
    continue
  tree = treecfg
  break

conn = dxr_server.connect_db(tree)

print 'Content-Type: application/json\n'

if 'query' in form:
  querytype = form['query']
else:
  querytype = 'fts'

if 'string' in form:
  json = json.JsonOutput(outfd=sys.stdout)

  if querytype == 'fts' or querytype == 'regex':
    prevpath = None
    json.open_list()

    if querytype == 'regex':
      matches = queries.getRegexMatches(conn, form['string'])
    else:
      matches = queries.getFTSMatches(conn, form['string'])

    for row in matches:
      if prevpath is None or prevpath != row[0]:
        if prevpath is not None:
          json.close_list()
          json.close()

        json.open()
        json.add ('path', row[0])
        json.key('matches')
        json.open_list()

      json.add(None, row[1])
      prevpath = row[0]

    json.close_list()
    json.close()
    json.close_list()
  elif querytype == 'files':
    json.open_list()

    for row in queries.getFileMatches(conn, form['string']):
      json.add(None, row[0])

    json.close_list()
  elif querytype == 'macros':
    json.open_list()

    for row in queries.getMacroMatches(conn, form['string']):
      json.open()
      json.add('def', row[0])
      json.add('path', row[1])
      json.add('line', row[2])
      json.close()

    json.close_list()
  elif querytype == 'functions':
    json.open_list()

    for row in queries.getFunctionMatches(conn, form['string']):
      json.open()
      json.add('def', row[0])
      json.add('args', row[1])
      json.add('type', row[2])
      json.add('path', row[3])
      json.add('line', row[4])
      json.close()

    json.close_list()
  elif querytype == 'variables':
    json.open_list()

    for row in queries.getVariableMatches(conn, form['string']):
      json.open()
      json.add('name', row[0])
      json.add('type', row[1])
      json.add('path', row[2])
      json.add('line', row[3])
      json.close()

    json.close_list()
  elif querytype == 'warnings':
    json.open_list()

    for row in queries.getWarningMatches(conn, form['string']):
      json.open()
      json.add('message', row[0])
      json.add('path', row[1])
      json.add('line', row[2])
      json.close()

    json.close_list()
  elif querytype == 'callers':
    json.open_list()

    for row in queries.getCallers(conn, form['string']):
      json.open()
      json.add('name', row[0])
      json.add('path', row[1])
      json.add('line', row[2])
      json.close()

    json.close_list()
