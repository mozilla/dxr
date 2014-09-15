"""Core, non-language-specific features of DXR, implemented as a Plugin"""

from funcy import identity
from jinja2 import Markup

from dxr.exceptions import BadQuery
import dxr.plugins
from dxr.plugins import FILE, LINE, Filter
from dxr.trigrammer import (regex_grammar, SubstringTreeVisitor, NGRAM_LENGTH,
                            And, JsRegexVisitor)
from dxr.utils import glob_to_regex


__all__ = ['mappings', 'analyzers', 'TextFilter', 'PathFilter']


# TODO: RegexFilter, ExtFilter, any needles for those


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
                'index': 'no',
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
            'filter': ['lowercase'],
            'tokenizer': 'trigram_tokenizer'
        },
        # And one for case-sensitive things:
        'trigramalyzer': {
            'tokenizer': 'trigram_tokenizer'
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

    def filter(self):
        positive = {
            'query': {
                'match_phrase': {
                    'content.trigrams' if self._term['case_sensitive']
                    else 'content.trigrams_lower': self._term['arg']
                }
            }
        }
        return {'not': positive} if self._term['not'] else positive

    def highlight_content(self, result):
        text_len = len(self._term['arg'])
        maybe_lower = (identity if self._term['case_sensitive'] else
                       lambda x: x.lower())
        return ((i, i + text_len) for i in
                # We assume content is a singleton. How could it be
                # otherwise?
                _find_iter(maybe_lower(result['content'][0]),
                           maybe_lower(self._term['arg'])))


def boolean_filter_tree(substrings, trigram_field):
    """Return a (probably nested) ES filter clause expressing the boolean
    constraints embodied in ``substrings``.

    :arg substrings: A SubstringTree
    :arg trigram_field: The ES property under which a trigram index of the
        field to match is stored

    """
    if isinstance(substrings, basestring):
        return {
            'query': {
                'match_phrase': {
                    trigram_field: substrings
                }
            }
        }
    return {
        'and' if isinstance(substrings, And) else 'or':
            [boolean_filter_tree(x, trigram_field) for x in substrings]
    }


def es_regex_filter(regex, raw_field, is_case_sensitive):
    """Return an efficient ES filter to find matches to a regex.

    Looks for fields of which ``regex`` matches a substring. (^ and $ do
    anchor the pattern to the beginning or end of the field, however.)

    :arg regex: A regex pattern as a string
    :arg raw_field: The name of an ES property to match against. The
        lowercase-folded trigram field is assumed to be
        raw_field.trigrams_lower, and the non-folded version
        raw_field.trigrams.
    :arg is_case_sensitive: Whether the match should be performed
        case-sensitive

    """
    trigram_field = ('%s.trigrams' if is_case_sensitive else
                     '%s.trigrams_lower') % raw_field
    parsed_regex = regex_grammar.parse(regex)
    substrings = SubstringTreeVisitor().visit(parsed_regex).simplified()

    # If tree is a string, just do a match_phrase. Otherwise, add .* to the
    # front and back, and build some boolean algebra.
    if isinstance(substrings, basestring) and len(substrings) < NGRAM_LENGTH:
        raise BadQuery('Regexps need 3 literal characters in a row for speed.')
        # We could alternatively consider doing an unaccelerated Lucene regex
        # query at this point. It would be slower but tolerable on a
        # moz-central-sized codebase: perhaps 500ms rather than 80.
    else:
        # Should be fine even if the regex already starts or ends with .*:
        js_regex = JsRegexVisitor().visit(parsed_regex)
        return {
            'and': [
                boolean_filter_tree(substrings, trigram_field),
                {
                    'script': {
                        'lang': 'js',
                        # test() tests for containment, not matching:
                        'script': '(new RegExp(pattern, flags)).test(doc["%s"].value)' % raw_field,
                        'params': {
                            'pattern': js_regex,
                            'flags': '' if is_case_sensitive else 'i'
                        }
                    }
                }
            ]
        }


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

    def filter(self):
        glob = self._term['arg']
        positive = es_regex_filter(
            glob_to_regex(glob),
            'path',
            is_case_sensitive=self._term['case_sensitive'])
        return {'not': positive} if self._term['not'] else positive


class TreeToIndex(dxr.plugins.TreeToIndex):
    def environment(self, vars):
        vars['source_folder'] = self.tree.source_folder
        vars['build_folder'] = self.tree.object_folder
        return vars

    def file_to_index(self, path, contents):
        return FileToIndex(path, contents, self.tree)


class FileToIndex(dxr.plugins.FileToIndex):
    def needles(self):
        """Fill out path (and path.trigrams)."""
        yield 'path', self.path
        # TODO: Add extension as a separate field (and to the mapping)?

    def needles_by_line(self):
        """Fill out line number and content for every line."""
        for number, text in enumerate(self.contents.splitlines(), 1):
            yield [('number', number),
                   ('content', text)]
