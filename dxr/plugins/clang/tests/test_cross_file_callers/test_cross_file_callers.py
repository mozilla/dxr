"""Tests for calls that span files.

These used to be a problem when we built a (single-file--whoops!) call graph,
but we don't anymore, so we can probably delete this at some point.

"""
from dxr.testing import DxrInstanceTestCase


class CrossFileCallerTests(DxrInstanceTestCase):
    def test_callers(self):
        """Make sure a "caller" needle is laid down at the callsite, pointing
        to the called function."""
        self.found_line_eq('callers:another_file(int)',
                           u'int a = <b>another_file(blah)</b>;',
                           5)
