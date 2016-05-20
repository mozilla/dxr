from nose.tools import eq_

from dxr.testing import DxrInstanceTestCase


class PathPromotionTests(DxrInstanceTestCase):
    """Test that path promotion finds paths and text, and in the correct order."""

    def test_ordering(self):
        """Test that a 'sub' search will find both filenames and contents containing sub,
        and that the exact file sub will be listed first."""
        results = self.search_results('sub', is_case_sensitive=False)
        # Make sure that the file `sub` is the first promoted match
        eq_(results[0],
            {u'path': u'subfolder/sub', u'lines': [],
            u'icon': u'unknown'})
        # Include line results for 'sub'
        eq_(results[3:], [
            {u'path': u'subfolder/sub',
             u'lines': [{u'line_number': 1, u'line': u'<b>Sub</b>'}],
             u'icon': u'unknown'},
            {u'path': u'subfolder/subfile',
             u'lines': [{u'line_number': 1, u'line': u'<b>Sub</b>file'}],
             u'icon': u'unknown'}])

    def test_case_sensitivity(self):
        """Test that a 'c.C' search will match c.c rather than ac.c if case insensitive."""
        results = self.search_results('c.C', is_case_sensitive=False)
        eq_(results, [
            # Make sure that the file `c.c` is the first promoted match
            {u'path': u'c.c', u'lines': [], u'icon': u'c'},
            {u'path': u'ac.c', u'lines': [], u'icon': u'c'}])
