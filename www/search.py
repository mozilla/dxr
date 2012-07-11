#!/usr/bin/env python2

import cgitb; cgitb.enable()
import cgi
import sqlite3
import sys
import os
import re, string

import dxr_server.fts

import dxr_server
from dxr_server.stopwatch import StopWatch
from dxr_server import queries
from dxr_server.queryparser import parse_query 
import dxr_server.query as query

# XXX: enable auto-flush on write - http://mail.python.org/pipermail/python-list/2008-June/668523.html
# reopen stdout file descriptor with write mode
# and 0 as the buffer size (unbuffered)
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

# Load query parameters
fieldStorage = cgi.FieldStorage()
form = dict((key, fieldStorage.getvalue(key)) for key in fieldStorage.keys())

print 'Content-Type: text/html\n'

tree = form['tree']
if tree not in dxr_server.trees:
  t = string.Template(dxr_server.getTemplateFile("dxr-search-header.html"))
  t = t.safe_substitute(title = 'Error',
                        tree = dxr_server.trees[0],
                        query = cgi.escape(form["q"], True))
  print t
  print '<h3>Error: Specified tree %s is invalid</h3>' % \
    ('tree' in form and cgi.escape(form['tree']) or tree)
  sys.exit (0)


conn = dxr_server.connect_db(tree)

# Parse the search query
q = parse_query(form.get("q", ""))

# Check that we got at least
if len(q["phrases"]) + len(q["keywords"]) + len(q["parameters"]) == 0:
  t = t.safe_substitute(title = 'Error',
                        tree = dxr_server.trees[0],
                        query = cgi.escape(form["q"], True))
  print t
  print '<h3>Error: unknown search parameters</h3>'
else:
  t = string.Template(dxr_server.getTemplateFile("dxr-search-header.html"))
  print t.safe_substitute(tree = tree,
                          query = cgi.escape(form["q"], True),
                          title = cgi.escape(form["q"], True))
  # Print sidebar before this
  # TODO: This should be a template thingy...
  print '<div id="content">'
  # Get the first 100 results
  found_results = False
  for path, lines in query.fetch_results(conn, q, 100, 0):
    found_results = True
    print string.Template("""
      <div class="searchfile"><a href="$virtroot/$tree/$path">$filename</a></div>
      <ul class="searchresults">
    """).safe_substitute(
              virtroot = dxr_server.virtroot,
              tree = tree,
              path = path,
              filename = os.path.basename(path)
              )
    for number, line in lines:
      cgi.escape(line)
      print string.Template("""
        <li class="searchresult"><a
        href="$virtroot/$tree/$path#l$number">$number:</a>&nbsp;&nbsp;$line</li>
      """).safe_substitute(
              virtroot = dxr_server.virtroot,
              tree = tree,
              path = path,
              number = number,
              line = line
              )
    print "</ul>"
  if not found_results:
    print "<p>No files matching the query was found.</p>"

print dxr_server.getTemplateFile("dxr-search-footer.html")
