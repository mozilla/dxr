import dxr.plugins
import pygments
import pygments.lexers
import pygments.lexer
import re
from pygments.token import Token, Comment
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

# Extend the Pygments Javascript lexer to handle preprocessor directives.
class JavascriptPreprocLexer(pygments.lexers.JavascriptLexer):
    """
    For Javascript with Mozilla build preprocessor directives.
    See https://developer.mozilla.org/en-US/docs/Build/Text_Preprocessor .
    """

    name = 'JavaScriptPreproc'
    aliases = []
    filenames = []
    mimetypes = []

    flags = re.DOTALL
    tokens = {
        'commentsandwhitespace': [
            # python-style comment
            (r'#\s.*?\n', Comment.Single),
            # preprocessor directives
            (r'#(includesubst|include|expand|define|undef|ifdef|ifndef|elifdef|'
             r'elifndef|if|elif|else|endif|filter|unfilter|literal|error)',
             Comment.Preproc),
            pygments.lexer.inherit
        ]
    }

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
    # TODO Enable C++ highlighting using pygments, pending fix for infinite
    # looping that we don't like, see:
    # https://bitbucket.org/birkenfeld/pygments-main/issue/795/
    if any((path.endswith(e) for e in ('.c', '.cc', '.cpp', '.cxx', '.h', '.hpp'))):
        return None
    # Options and filename
    options   = {'encoding': 'utf-8'}
    filename  = os.path.basename(path)
    lexer = None
    # Use a custom lexer for js/jsm files to highlight prepocessor directives
    if fnmatch.fnmatchcase(filename, "*.js") or fnmatch.fnmatchcase(filename, "*.jsm"):
        lexer = JavascriptPreprocLexer(**options)
    else:
        try:
            lexer = pygments.lexers.get_lexer_for_filename(filename, **options)
        except pygments.util.ClassNotFound:
            return None
    return Pygmentizer(text, lexer)

__all__ = dxr.plugins.htmlifier_exports()
