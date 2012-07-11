#!/usr/bin/env python2

"""
This is just a simple test server for DXR, NOT a deployment server.
Use apache or something else for deployments, this is NOT designed with security in mind.
NOTE: Support for mod_rewrite or something similar is quite important.
"""

import os, BaseHTTPServer, CGIHTTPServer, dxr_server

#Extension maps for DXRRequestHandler, sets them depending on context
#A hack that makes this work nicely.
everything_is_html = {'': "text/html"}

class DXRRequestHandler(CGIHTTPServer.CGIHTTPRequestHandler):
  def do_GET(self):
    # Just cut away the virtual root if any
    self.path = self.path[len(dxr_server.virtroot):]
    # Handle as default if /search or /static
    # /static urls will be served as static content
    # /search urls will be served as CGI, see is_cgi
    if self.path.startswith("/search") or self.path.startswith("/static") or self.path.startswith("/favicon"):
      CGIHTTPServer.CGIHTTPRequestHandler.do_GET(self)
    else:
      self.extension_map = everything_is_html
      # Add .html to path if not in /static or /search and do default
      # Essentially, this is equivalent to mod_rewrite where we add .html
      # for everything that isn't /static or /search
      path = self.translate_path(self.path)
      if not os.path.isdir(path):
        p = self.path.split("?", 1)
        if len(p) > 1:
          self.path = p[0] + ".html?" + p[1]
        else:
          self.path = p[0] + ".html"
      print self.path
      CGIHTTPServer.CGIHTTPRequestHandler.do_GET(self)
  
  def is_cgi(self):
    # If startswith search handle as CGI script
    if self.path.startswith('/search'):
      path = self.path.split('?')[0]
      if self.path.startswith('/search.cgi'):
        self.cgi_info = (os.path.dirname(path), os.path.basename(self.path))
      else:
        self.cgi_info = ("/", "search.py?" + self.path.split('?')[1])
      return True
    return False

def main():
  server_address = ('', 8000)
  server = BaseHTTPServer.HTTPServer(server_address, DXRRequestHandler)
  try:
    print "Starting test-server!"
    server.serve_forever()
  except KeyboardInterrupt:
    server.socket.close()

if __name__ == '__main__':
  main()
