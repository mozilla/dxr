"""Tests for calls that span files.

These used to be a problem when we built a (single-file--whoops!) call graph,
but we don't anymore, so we can probably delete this at some point.

"""
from dxr.testing import DxrInstanceTestCase

from nose import SkipTest


class CrossFileCallerTests(DxrInstanceTestCase):
    def test_callers(self):
        """Make sure a "caller" needle is laid down at the callsite, pointing
        to the called function."""
        raise SkipTest('Inter-file call lookup table is not yet implemented.')
        self.found_line_eq('callers:another_file',
                           u'int <b>main</b>(int argc, char* argv[]) {',
                           3)
