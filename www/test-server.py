#!/usr/bin/env python2

"""
This is just a simple test server for DXR, NOT a deployment server.
Use apache or something else for deployments, this is NOT designed with security in mind.
NOTE: Support for mod_rewrite or something similar is quite important.
"""

import os, BaseHTTPServer, CGIHTTPServer
from ConfigParser import ConfigParser
config = ConfigParser()
config.read(['/etc/dxr/dxr.config', './dxr.config'])
virtroot = config.get('Web', 'virtroot')
if virtroot[-1] == '/':
  virtroot = virtroot[:-1]

#Extension maps for DXRRequestHandler, sets them depending on context
#A hack that makes this work nicely.
everything_is_html = {'': "text/html"}

class DXRRequestHandler(CGIHTTPServer.CGIHTTPRequestHandler):
  def do_GET(self):
    # Just cut away the virtual root if any
    self.path = self.path[len(virtroot):]
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
        self.path += ".html"
      CGIHTTPServer.CGIHTTPRequestHandler.do_GET(self)
  
  def is_cgi(self):
    # If startswith search handle as CGI script
    if self.path.startswith('/search'):
      path = self.path.split('?')[0]
      self.cgi_info = (os.path.dirname(path), os.path.basename(self.path))
      return True
    return False

def main():
  server_address = ('', 8000)
  server = BaseHTTPServer.HTTPServer(server_address, DXRRequestHandler)
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    server.socket.close()

if __name__ == '__main__':
  main()
