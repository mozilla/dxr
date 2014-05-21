"""Just some screwing around with ES to find a doc shape that works"""

from time import localtime, strftime
from unittest import TestCase

from pyelasticsearch import ElasticSearch, ElasticHttpNotFoundError
from more_itertools import chunked
from nose.tools import eq_

from dxr.utils import connect_db


TEST_INDEX = 'dxr_test'
LINE = 'line'


# 1. Index just lines.
# 2. Delete the index, and then index lines + functions. Compare sizes.


def index_lines(lines):
    for path, line_id, number, text in lines:
        text = unicode(text, encoding='utf-8', errors='ignore')
        yield dict(
           id=line_id,
           path=path,
           path_trg=path,
           number=number,
           content=text,
           content_trg=text)


class ElasticSearchTests(TestCase):
    def setUp(self):
        pass
# To test:
# * Search for just file names based on a path prefix.
# * Search for just file names using arbitrary globs. That's no worse than what SQLite did if there's a static prefix, and it's more parallelizable. (Translate to regexes. Use trigram filter optionally.)
# * Search for lines from a file based on a path prefix (and some line content or whatever).
# * Search for structural elements.
# * Search for regexes, accelerated by trigrams. (Also, time unaccelerated regexes for comparison.)
# * Do case-sensitive and insensitive queries for both text and structural elements.

# Highlighting: does it work?
# V Phrase matching of trigrams: does it really work? YES.
# Do I want to keep a separate case-sensitive trigram index around for case-sensitive substring searching so I can avoid scanning through the candidate docs at all?
# Does trigram filtering accelerate wildcard queries? Not obviously on 1M docs. If this persists, consider trying post_filter to force the wildcard query to run last.
# Regex queries?

    def test_path_prefix(self):
        pass
        # eq_(self.es.search(index=TEST_INDEX, doc_type=LINE, body={
        #
        # },
        # {'foo': 'bar'})

# I get about 10K docs/s indexed, even over HTTP. That'll get us to 15M in 30 minutes. So ES indexing won't be the bottleneck.


if __name__ == '__main__':
    es = ElasticSearch('http://10.0.2.2:9200')
    try:
        es.delete_index(TEST_INDEX)
    except ElasticHttpNotFoundError:
        pass
    es.create_index(TEST_INDEX, settings={
        'settings': {
            'index': {
                'number_of_shards': 5,
                'number_of_replicas': 0
            },
            'analysis': {
                'analyzer': {
                    # A lowercase trigram analyzer. This is probably good
                    # enough for accelerating regexes; we probably don't
                    # need to keep a separate case-senitive index.
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
        },
        'mappings': {
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
                        'index': 'not_analyzed'
                    },
                    'content_trg': {
                        'type': 'string',
                        'analyzer': 'trigramalyzer'
                    },
                    # Type definitions
                    # Short name (not fully qualified)
                    'type': {
                        'type': 'string',
                        'index': 'not_analyzed'  # case-sensitive atm. Good?
                    },
                    'type_fq': {
                        'type': 'string',
                        'index': 'not_analyzed'  # case-sensitive atm. Good?
                    }
                }
            }
        }
    })

    # Maybe the clang plugin leaves everything about one file in a single temp file, and we don't need SQLite as an intermediary to avoid running out of RAM.
    conn = connect_db('/home/vagrant/moz-central/target/trees/mozilla-central')
    max_id = int(next(conn.execute('select max(id) from lines'))[0])
    CHUNK_SIZE = 10000
    for start in xrange(1, max_id, CHUNK_SIZE):
        print strftime("%a, %d %b %Y %H:%M:%S", localtime()), 'Starting chunk beginning at', start
        lines = conn.execute('select files.path, lines.id, lines.number, trg_index.text from lines inner join files on lines.file_id=files.id inner join trg_index on lines.id=trg_index.id where lines.id>=? and lines.id<?', [start, start + CHUNK_SIZE])
        for piece in chunked(index_lines(lines), 500):
            es.bulk_index(TEST_INDEX, LINE, piece)

    # Arrays sound like the perfect fit for structural elements. They map to Lucene multi-values, which I bet are like text fields except that nothing has any position. And we don't care about position. Make sure array searches act like we hope.
    # See if ES will highlight the region matched by a regex. That would be nice. Otherwise, we'll do it app-side. NOPE, it won't.
    # Let's see how big this DB gets with the trigram index. NOT THAT BIG.
