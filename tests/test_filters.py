"""Tests for filter code not specific to any filter"""

from unittest import TestCase

from nose.tools import eq_

from dxr.filters import LocalNamer
from dxr.query import alias_counter


class LocalNamerTests(TestCase):
    def test_basic(self):
        """Test replacement of single-char tokens without touching others."""
        namer = LocalNamer(alias_counter())
        eq_(namer.format('{a} {b} {nope}', nope='nah'),
            't0 t1 nah')
