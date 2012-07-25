#!/usr/bin/env python2

import dxr.plugins
import pygments
import pygments.lexers
from pygments.token import Token
import os, sys

def can_use(treecfg):
  return True

def post_process(srcdir, objdir):
  pass

def build_database(conn, srcdir, objdir, cache = None):
  pass

def pre_html_process(treecfg, blob):
  pass

def sqlify(blob):
  pass

def can_use(treecfg):
  return True # Yes you can always add syntax highlighting

def get_schema():
  return ''

def LexWrapper(alias):
  lexer = pygments.lexers.get_lexer_by_name(alias, encoding = "utf-8")
  def get_syntax_regions(blob, srcpath, treecfg, conn=None, dbpath=None):
    with open(srcpath, 'r') as f:
      data = f.read()
    for index, token, text in lexer.get_tokens_unprocessed(data):
      cls = None
      if token is Token.Keyword:
        cls = 'k'
      if token is Token.Name:
        cls = None
      if token is Token.Literal:
        cls = None
      if token is Token.String:
        cls = 'str'
      if token is Token.Operator:
        cls = None
      if token is Token.Punctuation:
        cls = None
      if token is Token.Comment:
        cls = 'c'
      if cls:
        yield (index, index + len(text), cls)
  return get_syntax_regions

# Create htmlifier for each support filetype
exclude = ('.c', '.cc', '.cpp', '.h', '.hpp')
htmlifiers = {}
for name, aliases, filetypes, mimetypes in pygments.lexers.get_all_lexers():
  filetypes = [s.strip("*") for s in filetypes]
  if any((s in exclude for s in filetypes)): continue
  if len(filetypes) == 0: continue
  lexWrap = LexWrapper(aliases[0])
  for ext in filetypes:
    htmlifiers[ext] = {"get_syntax_regions": lexWrap}

def get_htmlifiers():
  return htmlifiers


__all__ = dxr.plugins.required_exports()
