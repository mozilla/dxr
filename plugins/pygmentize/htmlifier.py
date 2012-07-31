import dxr.plugins
import pygments
import pygments.lexers
from pygments.token import Token
import os, sys

class Pygmentizer:
  """ Pygmentizer add syntax regions for file """
  def __init__(self, text, lexer):
    self.text   = text
    self.lexer  = lexer
  def refs(self):
    return []
  def regions(self):
    for index, token, text in self.lexer.get_tokens_unprocessed(self.text):
      cls = None
      if token is Token.Keyword:          cls = 'k'
      if token is Token.Name:             cls = None
      if token is Token.Literal:          cls = None
      if token is Token.String:           cls = 'str'
      if token is Token.Operator:         cls = None
      if token is Token.Punctuation:      cls = None
      if token is Token.Comment:          cls = 'c'
      if cls:   yield index, index + len(text), cls
  def annotations(self):
    return []
  def links(self):
    return []

def htmlify(tree, conn, path, text):
  options   = {'encoding': 'utf-8'}
  filename  = os.path.basename(path)
  try:
    lexer = pygments.lexers.get_lexer_for_filename(filename, **options)
  except pygments.util.ClassNotFound:
    # TODO Note this filename in some auxiliary log-file
    return None
  return Pygmentizer(text, lexer)

__all__ = dxr.plugins.htmlifier_exports()
