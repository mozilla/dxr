#!/usr/bin/env python2
import cgitb; cgitb.enable()
import cgi
import sqlite3
import sys, os

import config
import utils
import query

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

# Decide if we can redirect
can_redirect = querystring.get("redirect", "true") == "true"

# Find the offset and limit
# TODO Handle parsing errors that could occur here
offset = int(querystring.get("offset", 0))
limit  = int(querystring.get("limit", 100))


# Get and validate tree
tree = querystring.get('tree')
if tree not in config.trees:
  # Arguments for the template
  arguments = {
    # Common Template Variables
    "wwwroot":          config.wwwroot,
    "tree":             config.trees[0],
    "trees":            config.trees,
    "generated_date":   config.generated_date,
    "config":           config.template_parameters,
    # Error template Variables
    "error":            "Tree '%s' is not a valid tree." % tree
  }
  template = "error.html"
else:
  # Parse the search query
  q = query.Query(querystring.get("q", ""))
  # Connect to database
  conn = utils.connect_db(tree)
  # Arguments for the template
  arguments = {
    # Common Template Variables
    "wwwroot":        config.wwwroot,
    "tree":           tree,
    "trees":          config.trees,
    "config":         config.template_parameters,
    "generated_date": config.generated_date
  }
  if conn:
    result = None
    if can_redirect:
      result = query.direct_result(conn, q)
    if result:
      path, line = result
      print 'Content-Type: text/html\n'
      redirect = """
        <html>
          <head>
            <meta http-equiv='REFRESH' content='0;url=%s/%s/%s?from=%s#l%i'>
          </head>
        </html>
      """
      q_escape = cgi.escape(querystring.get("q", ""), True)
      print redirect % (config.wwwroot, tree, path, q_escape, line)
      sys.exit(0)
    # Okay let's try to make search results
    template = "search.html"
    # Catching any errors from sqlite, typically, regexp errors
    error = None
    try:
      results = list(query.fetch_results(
        conn, q,
        offset, limit
      ))
    except sqlite3.OperationalError, e:
      if e.message.startswith("REGEXP:"):
        arguments["error"] = e.message[7:]
        results = []
      elif e.message.startswith("QUERY:"):
        arguments["error"] = e.message[6:]
        results = []
      else:
        arguments["error"] = "Database error '%s'" % e.message
        template = "error.html"
    if template == "search.html":
      # Search Template Variables
      arguments["query"]            = cgi.escape(querystring.get("q", ""), True)
      arguments["results"]          = results
      arguments["offset"]           = offset
      arguments["limit"]            = limit
  else:
    arguments["error"] = "Failed to establish database connection."
    template = "error.html"

# If json is specified output as json
if output_format == "json":
  #TODO Return 503 if template == "error.html"
  print 'Content-type: application/json\n'
  import json
  # Tuples are encoded as lists in JSON, and these are not real
  # easy to unpack or read in Javascript. So for ease of use, we
  # convert to dicitionaries before returning the json results.
  arguments["results"] = [
      {
        "icon":   icon,
        "path":   path,
        "lines":  [{"line_number": nb, "line": l} for nb, l in lines]
      } for icon, path, lines in arguments["results"]]
  json.dump(arguments, sys.stdout, indent = 2)
  sys.exit(0)

# Print content-type
print 'Content-Type: text/html\n'

# Load template system
import jinja2
env = jinja2.Environment(
    loader          = jinja2.FileSystemLoader("template"),
    auto_reload     = False,
    bytecode_cache  = jinja2.FileSystemBytecodeCache("jinja_dxr_cache", "%s.cache")
)

# Get search template and dump it to stdout
env.get_template(template).stream(**arguments).dump(sys.stdout, encoding = "utf-8")
