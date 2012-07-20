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

# Get output format
output_format = querystring.get("format", "html")
if output_format not in ("html", "json"):
  output_format = "html"

# Get and validate tree
tree = querystring.get('tree')
if tree not in dxr_server.trees:
  # Arguments for the template
  arguments = {
    # Common Template Variables
    "wwwroot":    dxr_server.virtroot,
    "tree":       dxr_server.trees[0],
    "trees":      dxr_server.trees,
    # Error template Variables
    "error":      "Tree '%s' is not a valid tree." % tree
  }
  template = "error.html"
else:
  # Parse the search query
  q = dxr_server.query.Query(querystring.get("q", ""))
  # Connect to database
  conn = dxr_server.connect_db(tree)
  # Arguments for the template
  arguments = {
    # Common Template Variables
    "wwwroot":    dxr_server.virtroot,
    "tree":       tree,
    "trees":      dxr_server.trees
  }
  if conn:
    # Search Template Variables
    arguments["query"]    = cgi.escape(querystring.get("q", ""), True)
    arguments["results"]  = dxr_server.query.fetch_results(conn, q,
                                                           querystring.get("offset", 0),
                                                           querystring.get("limit", 100))
    arguments["offset"]   = querystring.get("offset", 0)
    arguments["limit"]    = querystring.get("limit", 100)
    template = "search.html"
  else:
    arguments["error"] = "Failed to establish database connection."
    template = "error.html"

# If json is specified output as json
if output_format == "json":
  print 'Content-type: application/json\n'
  import json
  # json doesn't like to serialize generators
  # and we don't really like tuples in javascript
  # so let's format it as objects instead of tuples
  arguments["results"] = [
      {
        "path":   path,
        "lines":  [{"line_number": line_nb, "line": line} for line_nb, line in lines]
      } for path, lines in arguments["results"]]
  json.dump(arguments, sys.stdout, indent = 2)
  sys.exit(0)

# Print content-type
print 'Content-Type: text/html\n'

# Load template system
import jinja2
env = jinja2.Environment(
    loader = jinja2.FileSystemLoader("dxr_server/templates"),
    auto_reload = False,
    bytecode_cache = jinja2.FileSystemBytecodeCache("dxr_server/jinja_dxr_cache", "%s.cache")
)

# Get search template and dump it to stdout
env.get_template(template).stream(**arguments).dump(sys.stdout, encoding = "utf-8")
