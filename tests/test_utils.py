from unittest import TestCase
from datetime import datetime

from nose.tools import eq_, assert_raises

from dxr.utils import deep_update, append_update, append_update_by_line, append_by_line, glob_to_regex, decode_es_datetime


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

