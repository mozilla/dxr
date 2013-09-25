from os.path import basename
from fnmatch import fnmatchcase

import pygments
import pygments.lexers
from pygments.token import Token

import dxr.plugins


token_classes = {
    Token.Keyword: 'k',
    Token.Keyword.Constant: 'k',
    Token.Keyword.Declaration: 'k',
    Token.Keyword.Namespace: 'k',
    Token.Keyword.Pseudo: 'k',
    Token.Keyword.Reserved: 'k',
    Token.Keyword.Type: 'k',
    Token.String: 'str',
    Token.String.Backtick: 'str',
    Token.String.Char: 'str',
    Token.String.Doc: 'str',
    Token.String.Double: 'str',
    Token.String.Escape: 'str',
    Token.String.Heredoc: 'str',
    Token.String.Interpol: 'str',
    Token.String.Other: 'str',
    Token.String.Regex: 'str',
    Token.String.Single: 'str',
    Token.String.Symbol: 'str',
    Token.Comment: 'c',
    Token.Comment.Multiline: 'c',
    Token.Comment.Single: 'c',
    Token.Comment.Special: 'c',
    Token.Comment.Preproc: 'p'}


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
    # TODO Enable C++ highlighting using pygments, pending fix for infinite
    # looping that we don't like, see:
    # https://bitbucket.org/birkenfeld/pygments-main/issue/795/
    if any((path.endswith(e) for e in ('.c', '.cc', '.cpp', '.cxx', '.h', '.hpp'))):
        return None
    # Options and filename
    options = {'encoding': 'utf-8'}
    filename = basename(path)
    try:
        lexer = pygments.lexers.get_lexer_for_filename(filename, **options)
    except pygments.util.ClassNotFound:
        # Small hack for js highlighting of jsm files
        if fnmatchcase(filename, "*.jsm"):
            lexer = pygments.lexers.JavascriptLexer(**options)
        else:
            return None
    return Pygmentizer(text, lexer)


__all__ = dxr.plugins.htmlifier_exports()
