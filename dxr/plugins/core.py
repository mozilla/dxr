"""Core, non-language-specific features of DXR, implemented as a Plugin"""

from os.path import splitext
import re

from funcy import identity
from jinja2 import Markup
from parsimonious import ParseError

from dxr.exceptions import BadTerm
from dxr.filters import Filter, negatable, FILE, LINE
import dxr.indexers
from dxr.plugins import direct_search
from dxr.trigrammer import (regex_grammar, SubstringTreeVisitor, NGRAM_LENGTH,
                            And, JsRegexVisitor, es_regex_filter, NoTrigrams,
                            PythonRegexVisitor)
from dxr.utils import glob_to_regex


__all__ = ['mappings', 'analyzers', 'TextFilter', 'PathFilter', 'ExtFilter',
           'RegexpFilter']


PATH_MAPPING = {  # path/to/a/folder/filename.cpp
    'type': 'string',
    'index': 'not_analyzed',  # support JS source fetching & sorting
    'fields': {
        'trigrams_lower': {
            'type': 'string',
            'analyzer': 'trigramalyzer_lower'  # accelerate wildcards
        },
        'trigrams': {
            'type': 'string',
            'analyzer': 'trigramalyzer'
        }
    }
}


EXT_MAPPING = {
    'type': 'string',
    'index': 'not_analyzed'
}


mappings = {
    # We also insert entries here for folders. This gives us folders in dir
    # listings and the ability to find matches in folder pathnames.
    FILE: {
        '_all': {
            'enabled': False
        },
        'properties': {
            # FILE filters query this. It supports globbing via JS regex script.
            'path': PATH_MAPPING,

            'ext': EXT_MAPPING,

            # Folder listings query by folder and then display filename, size,
            # and mod date.
            'folder': {  # path/to/a/folder
                'type': 'string',
                'index': 'not_analyzed'
            },

            'name': {  # filename.cpp or leaf_folder (for sorting and display)
                'type': 'string',
                'index': 'not_analyzed'
            },
            'size': {  # not present for folders
                'type': 'integer',  # bytes
                'index': 'no'
            },
            'modified': {  # not present for folders
                'type': 'date',
                'index': 'no'
            },
            'is_folder': {
                'type': 'boolean'
            }
        }
    },

    # The line doctype is the main workhorse of DXR searches. The search
    # results present lines, so that's what we index.
    LINE: {
        '_all': {
            'enabled': False
        },
        'properties': {
            'path': PATH_MAPPING,
            'ext': EXT_MAPPING,
            # TODO: After the query language refresh, use match_phrase_prefix
            # queries on non-globbed paths, analyzing them with the path
            # analyzer, for max perf. Perfect! Otherwise, fall back to trigram-
            # accelerated substring or wildcard matching.

            'number': {
                'type': 'integer'
            },

            # We index content 2 ways to keep RAM use down. Naively, we should
            # be able to pull the content.trigrams_lower source out using our
            # JS regex script, but in actuality, that uses much more RAM than
            # pulling just plain content, to the point of crashing.
            'content': {
                'type': 'string',
                'index': 'not_analyzed',  # support JS source fetching
                'fields': {
                    'trigrams_lower': {
                        'type': 'string',
                        'analyzer': 'trigramalyzer_lower'
                    },
                    'trigrams': {
                        'type': 'string',
                        'analyzer': 'trigramalyzer'
                    }
                }
            }
        }
    }
}


analyzers = {
    'analyzer': {
        # A lowercase trigram analyzer. This is probably good
        # enough for accelerating regexes; we probably don't
        # need to keep a separate case-sensitive index.
        'trigramalyzer_lower': {
            'type': 'custom',
            'filter': ['lowercase'],
            'tokenizer': 'trigram_tokenizer'
        },
        # And one for case-sensitive things:
        'trigramalyzer': {
            'type': 'custom',
            'tokenizer': 'trigram_tokenizer'
        },
        'lowercase': {  # Not used here but defined for plugins' use
            'type': 'custom',
            'filter': ['lowercase'],
            'tokenizer': 'keyword'
        }
    },
    'tokenizer': {
        'trigram_tokenizer': {
            'type': 'nGram',
            'min_gram': NGRAM_LENGTH,
            'max_gram': NGRAM_LENGTH
            # Keeps all kinds of chars by default.
        }
    }
}


def _find_iter(haystack, needle):
    """Return an iterable of indices at which string ``needle`` is found in
    ``haystack``.

    :arg haystack: The unicode string to search within
    :arg needle: The unicode string to search for

    Return only the first of overlapping occurrences.

    """
    if needle:
        needle_len = len(needle)
        offset = 0
        while True:
            offset = haystack.find(needle, offset)
            if offset == -1:
                break
            yield offset
            offset += needle_len


class TextFilter(Filter):
    """Filter matching a run of plain text in a file"""

    name = 'text'

    @negatable
    def filter(self):
        text = self._term['arg']
        if len(text) < NGRAM_LENGTH:
            return None
        return {
            'query': {
                'match_phrase': {
                    'content.trigrams' if self._term['case_sensitive']
                    else 'content.trigrams_lower': text
                }
            }
        }

    def highlight_content(self, result):
        text_len = len(self._term['arg'])
        maybe_lower = (identity if self._term['case_sensitive'] else
                       lambda x: x.lower())
        return ((i, i + text_len) for i in
                # We assume content is a singleton. How could it be
                # otherwise?
                _find_iter(maybe_lower(result['content'][0]),
                           maybe_lower(self._term['arg'])))


class PathFilter(Filter):
    """Substring filter for paths

    Pre-ES parity dictates that this simply searches for paths that have the
    argument as a substring. We may allow anchoring and such later.

    """
    name = 'path'
    domain = FILE
    description = Markup('File or directory sub-path to search within. <code>*'
                         '</code>, <code>?</code>, and <code>[...]</code> act '
                         'as shell wildcards.')

    @negatable
    def filter(self):
        glob = self._term['arg']
        try:
            return es_regex_filter(
                regex_grammar.parse(glob_to_regex(glob)),
                'path',
                is_case_sensitive=self._term['case_sensitive'])
        except NoTrigrams:
            raise BadTerm('Path globs need at least 3 literal characters in a row '
                          'for speed.')


class ExtFilter(Filter):
    """Case-sensitive filter for exact matching on file extensions"""

    name = 'ext'
    domain = FILE
    description = Markup('Filename extension: <code>ext:cpp</code>. Always '
                         'case-sensitive.')

    @negatable
    def filter(self):
        extension = self._term['arg']
        return {
            'term': {'ext': extension[1:] if extension.startswith('.')
                            else extension}
        }


class RegexpFilter(Filter):
    """Regular expression filter for file content"""

    name = 'regexp'
    description = Markup(r'Regular expression. Examples: '
                         r'<code>regexp:(?i)\bs?printf</code> '
                         r'<code>regexp:"(three|3) mice"</code>')

    def __init__(self, term):
        """Compile the Python equivalent of the regex so we don't have to lean
        on the regex cache during highlighting.

        Python's regex cache is naive: after it hits 100, it just clears: no
        LRU.

        """
        super(RegexpFilter, self).__init__(term)
        try:
            self._parsed_regex = regex_grammar.parse(term['arg'])
        except ParseError:
            raise BadTerm('Invalid regex.')
        self._compiled_regex = (
                re.compile(PythonRegexVisitor().visit(self._parsed_regex),
                           flags=0 if self._term['case_sensitive'] else re.I))

    @negatable
    def filter(self):
        try:
            return es_regex_filter(
                self._parsed_regex,
                'content',
                is_case_sensitive=self._term['case_sensitive'])
        except NoTrigrams:
            raise BadTerm('Regexes need at least 3 literal characters in a  '
                          'row for speed.')

    def highlight_content(self, result):
        return (m.span() for m in
                self._compiled_regex.finditer(result['content'][0]))


class TreeToIndex(dxr.indexers.TreeToIndex):
    def environment(self, vars):
        vars['source_folder'] = self.tree.source_folder
        vars['build_folder'] = self.tree.object_folder
        return vars

    def file_to_index(self, path, contents):
        return FileToIndex(path, contents, self.tree)


class FileToIndex(dxr.indexers.FileToIndex):
    def needles(self):
        """Fill out path (and path.trigrams)."""
        yield 'path', self.path
        extension = splitext(self.path)[1]
        if extension:
            yield 'ext', extension[1:]  # skip the period

    def needles_by_line(self):
        """Fill out line number and content for every line."""
        for number, text in enumerate(self.contents.splitlines(), 1):
            yield [('number', number),
                   ('content', text)]


# Match file name and line number: filename:n. Strip leading slashes because
# we don't have any in the index.
FILE_LINE_RE = re.compile("^/?(.+):([1-9][0-9]*)$")


def _file_and_line(term):
    """Return the pathname or filename and line number from a term with text
    in the format filename:line_num. Return None if the term isn't in that
    format.

    """
    match = FILE_LINE_RE.match(term['arg'])
    if match:
        return match.group(1), int(match.group(2))


@direct_search(priority=100)
def direct_path_and_line(term):
    """If the user types path:line_num, jump him right to that line.

    "path" can be any contiguous sequence of complete path segments; to match
    fee/fi/fo/fum.cpp, any of the following would work:

    * /fee/fi/fo/fum.cpp
    * fo/fum.cpp
    * fum.cpp

    """
    try:
        path, line = _file_and_line(term)
    except TypeError:
        return None

    if path.startswith('/'):
        # If path start with a /, the user is explicitly requesting a match
        # starting at the root level.
        path = path[1:]  # Leading slashes aren't stored in the index.
        regex = '^{0}$'  # Insist it start at the beginning.
    else:
        regex = '(/|^){0}$'  # Start at any path segment.

    try:
        trigram_clause = es_regex_filter(
                regex_grammar.parse(regex.format(re.escape(path))),
                'path',
                term['case_sensitive'])
    except NoTrigrams:
        return None

    return {
        'and': [
            trigram_clause,
            {'term': {'number': line}}
        ]
    }
