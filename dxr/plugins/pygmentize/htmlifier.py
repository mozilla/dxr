from os.path import basename
import re

import pygments
from pygments.lexers import get_lexer_for_filename, JavascriptLexer
from pygments.lexer import inherit
from pygments.token import Token, Comment

import dxr.plugins


token_classes = {Token.Comment.Preproc: 'p'}
token_classes.update((t, 'k') for t in [Token.Keyword,
                                        Token.Keyword.Constant,
                                        Token.Keyword.Declaration,
                                        Token.Keyword.Namespace,
                                        Token.Keyword.Pseudo,
                                        Token.Keyword.Reserved,
                                        Token.Keyword.Type])
token_classes.update((t, 'str') for t in [Token.String,
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
                                          Token.String.Symbol])
token_classes.update((t, 'c') for t in [Token.Comment,
                                        Token.Comment.Multiline,
                                        Token.Comment.Single,
                                        Token.Comment.Special])


# Extend the Pygments Javascript lexer to handle preprocessor directives.
class JavascriptPreprocLexer(JavascriptLexer):
    """
    For Javascript with Mozilla build preprocessor directives.
    See https://developer.mozilla.org/en-US/docs/Build/Text_Preprocessor .
    """

    name = 'JavaScriptPreproc'
    filenames = []
    mimetypes = []

    tokens = {
        'commentsandwhitespace': [
            # python-style comment
            (r'#\s[^\n]*\n', Comment.Single),
            # preprocessor directives
            (r'#(includesubst|include|expand|define|undef|ifdef|ifndef|elifdef|'
             r'elifndef|if|elif|else|endif|filter|unfilter|literal|error)',
             Comment.Preproc),
            pygments.lexer.inherit
        ]
    }

class Pygmentizer(object):
    """Pygmentizer to apply CSS classes to syntax-highlit regions"""

    def __init__(self, text, lexer):
        self.text = text
        self.lexer = lexer

    def refs(self):
        return []

    def regions(self):
        for index, token, text in self.lexer.get_tokens_unprocessed(self.text):
            cls = token_classes.get(token)
            if cls:
                yield index, index + len(text), cls

    def annotations(self):
        return []

    def links(self):
        return []


def load(tree, conn):
    pass


def htmlify(path, text):
    # Options and filename
    options = {'encoding': 'utf-8'}
    filename = basename(path)

    # Use a custom lexer for js/jsm files to highlight prepocessor directives
    if filename.endswith('.js') or filename.endswith('.jsm'):
        lexer = JavascriptPreprocLexer(**options)
    else:
        try:
            # Lex .h files as C++ so occurrences of "class" and such get colored;
            # Pygments expects .H, .hxx, etc. This is okay even for uses of
            # keywords that would be invalid in C++, like 'int class = 3;'.
            lexer = get_lexer_for_filename('dummy.cpp' if filename.endswith('.h')
                                                       else filename,
                                           **options)
        except pygments.util.ClassNotFound:
            return None

    return Pygmentizer(text, lexer)


__all__ = dxr.plugins.htmlifier_exports()
