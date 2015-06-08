from os.path import basename

from pygments.lexers import get_lexer_for_filename, JavascriptLexer
from pygments.lexer import inherit
from pygments.token import Token, Comment
from pygments.util import ClassNotFound

import dxr.indexers


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
    """Lexer for Javascript with Mozilla build preprocessor directives.

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
            inherit
        ]
    }


def _lexer_for_filename(filename):
    """Return a Pygments lexer suitable for a file based on its extension.

    Return None if one can't be determined.

    """
    if filename.endswith('.js') or filename.endswith('.jsm'):
        # Use a custom lexer for js/jsm files to highlight prepocessor
        # directives
        lexer = JavascriptPreprocLexer()
    else:
        try:
            # Lex .h files as C++ so occurrences of "class" and such get colored;
            # Pygments expects .H, .hxx, etc. This is okay even for uses of
            # keywords that would be invalid in C++, like 'int class = 3;'.
            lexer = get_lexer_for_filename('dummy.cpp' if filename.endswith('.h')
                                                       else filename)
        except ClassNotFound:
            return None

    return lexer


def _regions_for_contents(lexer, contents):
    """Yield regions for the tokens in text contents using given Pygments lexer."""
    for index, token, text in lexer.get_tokens_unprocessed(contents):
        cls = token_classes.get(token)
        if cls:
            yield index, index + len(text), cls


class FileToIndex(dxr.indexers.FileToIndex):
    """Emitter of CSS classes for syntax-highlit regions"""

    def regions(self):
        lexer = _lexer_for_filename(basename(self.path))
        if lexer:
            return _regions_for_contents(lexer, self.contents)
        return []


class FileToSkim(dxr.indexers.FileToSkim):
    """Emitter of CSS classes for syntax-highlit regions"""

    def is_interesting(self):
        return not self.file_properties

    def regions(self):
        lexer = _lexer_for_filename(basename(self.path))
        if lexer:
            return _regions_for_contents(lexer, self.contents)
        return []

