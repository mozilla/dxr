# -*- coding: utf-8 -*-

from datetime import datetime

from nose.tools import eq_, assert_raises

from dxr.testing import TestCase
from dxr.utils import (DXR_BLUEPRINT, append_update, append_update_by_line,
                       append_by_line, browse_file_url, decode_es_datetime,
                       deep_update, glob_to_regex, search_url)


class DeepUpdateTests(TestCase):
    def test_mappings(self):
        """Make sure mapping-type values get merged."""
        dest = {
            'line': {
                'properties': {
                    'path': {  # A key will be added within this.
                        'type': 'string',
                        'index': 'not_analyzed'
                    }
                }  # A key will be added after this mapping-valued key.
            },
            'dash': {  # This key's value will be unchanged.
                'nothing': 'here'
            }
        }
        source = {
            'line': {
                'properties': {
                    'path': {
                        'new': 'thing'
                    }
                },
                'floperties': {
                    'a': 'flop'
                }
            }
        }
        eq_(deep_update(dest, source),
            {
                'line': {
                    'properties': {
                        'path': {
                            'type': 'string',
                            'index': 'not_analyzed',
                            'new': 'thing'
                        }
                    },
                    'floperties': {
                        'a': 'flop'
                    }
                },
                'dash': {
                    'nothing': 'here'
                }
            })

    def test_overwrites(self):
        """Non-mapping keys should be overwritten."""
        eq_(deep_update(dict(a=8), dict(a=9)), dict(a=9))

    def test_conflicts(self):
        """If types for a key don't agree, explode."""
        assert_raises(TypeError, deep_update, dict(a={}), dict(a=9))
        assert_raises(TypeError, deep_update, dict(a=9), dict(a={}))


def test_append_update():
    """Make sure existent key are merged and nonexistent ones are created as
    lists."""
    d = {'o': ['hai']}
    eq_(append_update(d, [('o', 'hello'), ('o', 'howdy'), ('p', 'pod')]),
        {'o': ['hai', 'hello', 'howdy'], 'p': ['pod']})


def test_append_update_by_line():
    eq_(append_update_by_line([{}, {'o': ['hai'], 'p': ['pod']}],
                              [[('q', 'bert')],
                               [('o', 'hi'), ('o', 'no'), ('p', 'diddy')]]),
        [{'q': ['bert']}, {'o': ['hai', 'hi', 'no'], 'p': ['pod', 'diddy']}])


def test_append_by_line():
    eq_(append_by_line([[], [6]],
                       [[5, 6], [7, 9]]),
        [[5, 6], [6, 7, 9]])


def test_glob_to_regex():
    """Make sure glob_to_regex() strips the right static suffix off the end of
    the pattern fnmatch.translate() returns.

    In other words, pin down the behavior of fnmatch.translate().

    """
    eq_(glob_to_regex('hi'), 'hi')


def test_decode_es_datetime():
    """Test that both ES datetime formats are decoded."""
    eq_(datetime(1992, 6, 27, 0, 0), decode_es_datetime("1992-06-27T00:00:00"))
    eq_(datetime(1992, 6, 27, 0, 0, 0), decode_es_datetime("1992-06-27T00:00:00.0"))


class UrlBuilderTests(TestCase):
    """Tests for the speed-optimized URL builders"""

    def test_tests(self):
        """Make sure these tests keep up with the canonical URLs."""
        eq_(self.url_for(DXR_BLUEPRINT + '.browse', tree='TREE', path='THE/PATH'),
            '/TREE/source/THE/PATH')
        eq_(self.url_for(DXR_BLUEPRINT + '.search', tree='TREE', q='QUERY'),
            '/TREE/search?q=QUERY')

    def test_browse_file_url(self):
        """Test unicode of various widths, slashes, and spaces."""
        with self.app().test_request_context():
            eq_(browse_file_url(u'tr éé', u'ev il:päthß/ªre/bes†', _anchor=4),
                '/tr%20%C3%A9%C3%A9/source/ev%20il%3Ap%C3%A4th%C3%9F/%C2%AAre/bes%E2%80%A0#4')

    def test_search_url(self):
        """Test unicode of various widths, slashes, and spaces."""
        with self.app().test_request_context():
            eq_(search_url(u'tr éé', u'ev il:searcheß/ªre/bes†'),
            '/tr%20%C3%A9%C3%A9/search?q=ev+il%3Asearche%C3%9F%2F%C2%AAre%2Fbes%E2%80%A0')
