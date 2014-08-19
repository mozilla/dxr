"""Core, non-language-specific features of DXR, implemented as a Plugin"""

import dxr.plugins
from dxr.plugins import FILE, LINE, Filter


# TODO: RegexFilter, ExtFilter, PathFilter, any needles for those


mappings = {
    # We also insert entries here for folders. This gives us folders in dir
    # listings and the ability to find matches in folder pathnames.
    FILE: {
        '_all': {
            'enabled': False
        },
        'properties': {
            # FILE filters query this. It supports globbing via JS regex script.
            'path': {  # path/to/a/folder/filename.cpp
                'type': 'string',
                'index': 'not_analyzed',  # support JS source fetching & sorting
                'fields': {
                    'trigrams': {
                        'type': 'string',
                        'analyzer': 'trigramalyzer'  # accelerate regexes
                    }
                }
            },

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
            'path': {
                'type': 'string',
                # TODO: What about case-insensitive?
                'index': 'not_analyzed',  # support sorting
                'fields': {
                    'trigrams': {
                        'type': 'string',
                        'analyzer': 'trigramalyzer'
                    }
                }
            },
            # TODO: Use match_phrase_prefix queries on non-globbed paths,
            # analyzing them with the path analyzer, for max perf. Perfect!
            # Otherwise, fall back to trigram-accelerated substring or wildcard
            # matching.

            'number': {
                'type': 'integer'
            },

            # We index content 2 ways to keep RAM use down. Naively, we should
            # be able to pull the content.trigrams source out using our JS
            # regex script, but in actuality, that uses much more RAM than
            # pulling just plain content, to the point of crashing.
            'content': {
                'type': 'string',
                'index': 'no',
                'fields': {
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
        'trigramalyzer': {
            'filter': ['lowercase'],
            'tokenizer': 'trigram_tokenizer'
        }
    },
    'tokenizer': {
        'trigram_tokenizer': {
            'type': 'nGram',
            'min_gram': 3,
            'max_gram': 3
            # Keeps all kinds of chars by default.
        }
    }
}


def _find_iter(haystack, needle):
    """Return an iterable of indices at which string ``needle`` is found in
    ``haystack``.

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
    domain = LINE

    def __init__(self, term):
        """Store the text we're searching for."""
        if term['case_sensitive']:
            # We might have to store a second trigram index to support this,
            # unlike with trilite.
            raise NotImplementedError
        self.text = term['arg']

    def filter(self):
        return {
            'query': {
                'match_phrase': {
                    'content.trigrams': self.text
                }
            }
        }

    def highlight(self, result, field):
        if field == 'content':
            text_len = len(self.text)
            return ((o, o + text_len) for o in
                    # We assume content is a singleton. How could it be
                    # otherwise?
                    _find_iter(result['content'][0].lower(),
                               self.text.lower()))
        else:
            return []


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
