"""Core, non-language-specific features of DXR, implemented as a Plugin"""

import dxr.plugins
from dxr.plugins import FILE, LINE


# TODO: path and ext filters, needles for those


mappings = {
    FILE: {
        '_all': {
            'enabled': False
        },
        'properties': {
            # FILE filters query this. It supports globbing via JS regex script.
            'path': {  # path/to/a/folder/filename.cpp
                'type': 'string',
                'index': 'no',  # support JS source fetching but not Wildcard queries
                'fields': {
                    'trigrams': {
                        'type': 'string',
                        'analyzer': 'trigramalyzer'  # accelerate regexes
                    }
                }
            },
            'size': {
                'type': 'integer',  # bytes
                'index': 'no'
            },
            'modified': {
                'type': 'date',
                'index': 'no'
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
            # pulling just plain content and crashes.
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
