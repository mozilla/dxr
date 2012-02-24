#!/usr/bin/env python2

import cgitb; cgitb.enable()
import ConfigParser
import sqlite3
import cgi
import sys
import os
import re
import ctypes

# Get the DXR installation point from dxr.config
config = ConfigParser.ConfigParser()
try:
  config.read(['/etc/dxr/dxr.config', './dxr.config'])
  sys.path.append(config.get('DXR', 'dxrroot'))
except:
  msg = sys.exc_info()[1] # Python 2/3 compatibility
  print 'Content-Type: text/html\n'
  print '<body><h3>Error: Failed to open either %s/dxr.config ' \
        'or /etc/dxr/dxr.config</h3><p>%s</body>' % (os.getcwd(), msg)
  sys.exit (0)
import dxr
from dxr import queries
from dxr import json

try:
  ctypes_init_tokenizer = ctypes.CDLL(config.get('DXR', 'dxrroot') + "/sqlite/libdxr-code-tokenizer.so").dxr_code_tokenizer_init
  ctypes_init_tokenizer ()
except:
  msg = sys.exc_info()[1] # Python 2/3 compatibility
  print "Could not load tokenizer: %s" % msg
  sys.exit (0)

def regexp(expr, item):
  reg = re.compile(expr)
  try:
    return reg.search(item) is not None
  except:
    return False

# Load query parameters
fieldStorage = cgi.FieldStorage()
form = dict((key, fieldStorage.getvalue(key)) for key in fieldStorage.keys())

try:
  dxrconfig = dxr.load_config()
except:
  msg = sys.exc_info()[1] # Python 2/3 compatibility
  print '<body><h3>Error: Failed to parse dxr.config ' \
        'or /etc/dxr/dxr.config</h3><p>%s</body>' % msg
  sys.exit (0)

for treecfg in dxrconfig.trees:
  if 'tree' in form and treecfg.tree != form['tree']:
    continue
  dxrconfig = treecfg
  tree = treecfg.tree
  break

try:
  # Load the database
  dbname = tree + '.sqlite'
  dxrdb = os.path.join(treecfg.dbdir, dbname)
  conn = sqlite3.connect(dxrdb)
  conn.text_factory = str
  conn.create_function ('REGEXP', 2, regexp)
  conn.execute('PRAGMA temp_store = MEMORY;')
  conn.execute('SELECT initialize_tokenizer()')
except:
  print 'Countent-Type: text/html\n'
  print '<body><h3>Error, failed to open database</h3><p>%s</body>' % (sys.exc_info()[1])
  sys.exit(0)

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
    
