from nose.tools import eq_

from dxr.testing import DxrInstanceTestCase


class PathPromotionTests(DxrInstanceTestCase):
    """Test that path promotion finds paths and text, and in the correct order."""

    def test_ordering(self):
        """Test that a 'sub' search will find both filenames and contents containing sub,
        and that the exact file sub will be listed first."""
        results = self.search_results('sub')
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
