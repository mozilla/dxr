#!/usr/bin/env python2
import cgitb; cgitb.enable()
import cgi
import sqlite3
import sys, os

import dxr_server
import dxr_server.query

# XXX: enable auto-flush on write - http://mail.python.org/pipermail/python-list/2008-June/668523.html
# reopen stdout file descriptor with write mode
# and 0 as the buffer size (unbuffered)
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

# Load query parameters
fieldStorage = cgi.FieldStorage()
querystring = dict((key, fieldStorage.getvalue(key)) for key in fieldStorage.keys())

# Print content-type
print 'Content-Type: text/html\n'

# Get and validate tree
tree = querystring.get('tree')
if tree not in dxr_server.trees:
  print '<h3>Error: Specified tree is invalid</h3>'
  sys.exit (0)

# Parse the search query
q = dxr_server.query.Query(querystring.get("q", ""))

# Connect to database
conn = dxr_server.connect_db(tree)

# Arguments for the template
arguments = {
    # Common Template Variables
    "wwwroot":    dxr_server.virtroot,
    "tree":       tree,
    "trees":      dxr_server.trees,
    # Search Template Variables
    "query":      cgi.escape(querystring.get("q", ""), True),
    "results":    dxr_server.query.fetch_results(
                      conn, q,
                      querystring.get("offset", 0),
                      querystring.get("limit", 100)
                  ),
    "offset":     querystring.get("offset", 0),
    "limit":      querystring.get("limit", 100)
    # Do NOT add variables without documentating them in templating.mkd
}

# Load template system
import jinja2
env = jinja2.Environment(
    loader = jinja2.FileSystemLoader("dxr_server/templates"),
    auto_reload = False,
    bytecode_cache = jinja2.FileSystemBytecodeCache("dxr_server/jinja_dxr_cache", "%s.cache")
)

# Get search template and dump it to stdout
env.get_template("search.html").stream(**arguments).dump(sys.stdout, encoding = "utf-8")
