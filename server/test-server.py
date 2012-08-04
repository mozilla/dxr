#!/usr/bin/env python2

# This file is a python string.Template and will be filled out by dxr-build.py,
# See create_server() foir details on what variables there is available.

"""
This is just a simple test server for DXR, NOT a deployment server.
Use apache or something else for deployments, this is NOT designed with security in mind.
NOTE: Support for mod_rewrite or something similar is quite important.
"""

import os, sys, BaseHTTPServer, CGIHTTPServer

port = 8000
if len(sys.argv) > 2 and sys.argv[1] == "--port":
  port = int(sys.argv[2])

#Extension maps for DXRRequestHandler, sets them depending on context
#A hack that makes this work nicely.
everything_is_html = {"": "text/html"}

class DXRRequestHandler(CGIHTTPServer.CGIHTTPRequestHandler):
  def do_GET(self):
    # Just cut away the wwwroot
    path = self.path[len($wwwroot):]
    CGIHTTPServer.CGIHTTPRequestHandler.do_GET(self)
    return

  def translate_path(self, path):
    # Just cut away the wwwroot and the /
    path = self.path[len($wwwroot) + 1:]
    p = path.split("?", 1)
    qstring = ""
    if len(p) > 1:
      path = p[0]
      qstring = '?' + p[1]
    if path.startswith('search'):
      return "search.py"
    elif path.startswith('static'):
      return 'template/' + path
    else:
      self.extensions_map = everything_is_html
      # Let's try to find the tree
      tree = None
      for t in $trees:
        if path.startswith(t):
          tree = t
          break
      if not tree:
        # We didn't get a tree
        return "index.html" + qstring
      else:
        path = path[len(tree):]
        if path.startswith("/"):
          path = path[1:]
        if os.path.isdir("../" + tree + "/" + path):
          return '../' + tree + '/' + path + "/" + $directory_index
        else:
          return '../' + tree + '/' + path + ".html"

  def is_cgi(self):
    # If startswith search handle as CGI script
    if self.path.startswith('/search'):
      path = self.path.split('?')[0]
      self.cgi_info = ("/", "search.py?" + self.path.split('?')[1])
      return True
    return False

def main():
  server_address = ('', port)
  server = BaseHTTPServer.HTTPServer(server_address, DXRRequestHandler)
  try:
    print "Starting test-server!"
    server.serve_forever()
  except KeyboardInterrupt:
    server.socket.close()

if __name__ == '__main__':
  main()
