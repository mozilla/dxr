"""Tests for calls that span files"""

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

    def test_called_by(self):
        """Make sure "called-by" needles get deposited at function definitions
        and refer to their call sites."""
