"""Core, non-language-specific features of DXR, implemented as a Plugin"""

import dxr.plugins
from dxr.plugins import FILE, LINE


# TODO: path and ext filters, needles for those


mappings = {
    # The file doctype exists solely to support folder listings, which query by
    # path and then display size and mod date.
    FILE: {
        '_all': {
            'enabled': False
        },
        'properties': {
            'path': {
                'type': 'string',
                'index': 'not_analyzed'
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
                'index': 'not_analyzed'  # TODO: What about case-insensitive?
            },
            'path_trg': {
                'type': 'string',
                'analyzer': 'trigramalyzer'
            },
            # TODO: Use match_phrase_prefix queries on non-globbed paths, analyzing them with the path analyzer, for max perf. Perfect! Otherwise, fall back to trigram-accelerated substring or wildcard matching.
            # TODO: Use multi-fields so we don't have to pass the text in twice on indexing.

            'number': {
                'type': 'integer'
            },

            'content': {
                'type': 'string',
                'index': 'no'
            },
            'content_trg': {
                'type': 'string',
                'analyzer': 'trigramalyzer'
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
        """Fill out path (and path_trg)."""
        yield 'path', self.path

    def needles_by_line(self):
        """Fill out line number and content for every line."""
        for number, text in enumerate(self.content.splitlines(), 1):
            yield [('number', number),
                   ('content', text)]
