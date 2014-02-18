"""Tests for emission of high-level markup, as by templates"""

from dxr.testing import DxrInstanceTestCase

from nose.tools import eq_, ok_


class MarkupTests(DxrInstanceTestCase):
    def test_autofocus_root(self):
        """Autofocus the query field at the root of each tree but not
        elsewhere."""
        response = self.client().get('/code/source/')
        ok_('<input type="text" name="q" autofocus' in response.data)

        response = self.client().get('/code/source/folder')
        eq_(response.status_code, 200)
        ok_('<input type="text" name="q" autofocus' not in response.data)
