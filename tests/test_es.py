"""Just some screwing around with ES to find a doc shape that works"""

from unittest import TestCase

from elasticsearch import Elasticsearch
from nose.tools import eq_


INDEX = 'dxr_test'


def ElasticSearchTests(TestCase):
    def setUp(self):
        es = self.es = ElasticSearch()
        select files.path, lines.id, trg_index.content, types.name from big join

        # Index left-ngrams of names of structural things. Then we can do as-you-type matches.
        es.indices.create(INDEX, {
            'settings': {
                'index': {
                    'number_of_shards': 5,
                    'number_of_replicas': 0
                },
                'analysis': {
                    'analyzer': {
                        # Index prefixes of strings at least 3 chars long.
                        'prefix': {
                            'tokenizer': 'edge_ngrammer'
                        },
                        # A lowercase trigram analyzer. This is probably good
                        # enough for accelerating regexes; we probably don't
                        # need to keep a separate case-senitive index.
                        'trigramalyzer': {
                            'filter': ['lowercase'],
                            'tokenizer': 'trigram_tokenizer'
                        }
                    },
                    'tokenizer': {
                        'edge_ngrammer': {
                            'type': 'edgeNGram',
                            'min_gram': 3,
                            'max_gram': 400  # ouch? Consider the path hierarchy tokenizer if this gets out of hand.
                            # Keeps all kinds of chars by default.
                        },
                        'trigram_tokenizer': {
                            'type': 'nGram',
                            'min_gram': 3,
                            'max_gram': 3
                            # Keeps all kinds of chars by default.
                        }
                    }
                }
            },
            'mappings': {
                'line': {
                    '_all': {
                        'enabled': False
                    },
                    'properties': {
                        'path': {
                            'type': 'string',
                            'analyzer': 'prefix'  # TODO: Remove. Use prefix queries instead.
                        },
                        'number': {
                            'type': 'int'
                        },
                        'content': {
                            'type': 'string',
                            'analyzer': 'trigramalyzer'
                        },
                        # Type definitions
                        # Short name (not fully qualified)
                        'type': {
                            'type': 'string',
                            'analyzer': 'prefix'
                        },
                        'type_fq': {
                            'type': 'string',
                            'index': 'not_analyzed'  # case-sensitive atm. Good?
                        }
                    }
                }
            }
        })
        es.bulk_index(dict(
            _id=id,
            path=path,
            content=content,
            types
        # Arrays sound like the perfect fit for structural elements. They map to Lucene multi-values, which I bet are like text fields except that nothing has any position. And we don't care about position.
        # See if ES will highlight the region matched by a regex. That would be nice. Otherwise, we'll do it app-side.
        # Let's see how big this DB gets with the trigram index.

# To test:
# * Search for just file names based on a path prefix.
# * Search for just file names using arbitrary globs. That's no worse than what SQLite did if there's a static prefix, and it's more parallelizable. (Translate to regexes. Use trigram filter optionally.)
# * Search for lines from a file based on a path prefix (and some line content or whatever).
# * Search for structural elements.
# * Search for regexes, accelerated by trigrams. (Also, time unaccelerated regexes for comparison.)
# * Do case-sensitive and insensitive queries for both text and structural elements.

    def test_path_prefix(self):
        eq_(self.es.search(index=INDEX, doc_type='lines', body={
        
        },
        {'foo': 'bar'})