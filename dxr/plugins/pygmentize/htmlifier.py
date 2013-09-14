import dxr.plugins
import pygments
import pygments.lexers
from pygments.token import Token
import os, sys
import fnmatch

keyword_tokens = [Token.Keyword,
                  Token.Keyword.Constant,
                  Token.Keyword.Declaration,
                  Token.Keyword.Namespace,
                  Token.Keyword.Pseudo,
                  Token.Keyword.Reserved,
                  Token.Keyword.Type]
string_tokens =  [Token.String,
                  Token.String.Backtick,
                  Token.String.Char,
                  Token.String.Doc,
                  Token.String.Double,
                  Token.String.Escape,
                  Token.String.Heredoc,
                  Token.String.Interpol,
                  Token.String.Other,
                  Token.String.Regex,
                  Token.String.Single,
                  Token.String.Symbol]
comment_tokens = [Token.Comment,
                  Token.Comment.Multiline,
                  Token.Comment.Single,
                  Token.Comment.Special]

class Pygmentizer(object):
    """ Pygmentizer add syntax regions for file """
    def __init__(self, text, lexer):
        self.text   = text
        self.lexer  = lexer
    def refs(self):
        return []
    def regions(self):
        for index, token, text in self.lexer.get_tokens_unprocessed(self.text):
            cls = None
            if token in keyword_tokens:        cls = 'k'
            if token in string_tokens:         cls = 'str'
            if token in comment_tokens:        cls = 'c'
            if token is Token.Comment.Preproc: cls = 'p'
            if cls:   yield index, index + len(text), cls
    def annotations(self):
        return []
    def links(self):
        return []


def load(tree, conn):
    pass

def htmlify(path, text):
    # Options and filename
    options   = {'encoding': 'utf-8'}
    filename  = os.path.basename(path)
    try:
        lexer = pygments.lexers.get_lexer_for_filename(filename, **options)
    except pygments.util.ClassNotFound:
        # Small hack for js highlighting of jsm files
        if fnmatch.fnmatchcase(filename, "*.jsm"):
            lexer = pygments.lexers.JavascriptLexer(**options)
        else:
            return None
    return Pygmentizer(text, lexer)

__all__ = dxr.plugins.htmlifier_exports()
