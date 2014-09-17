"""Tests for emission of high-level markup, as by templates"""

from dxr.testing import DxrInstanceTestCase, run

from nose.tools import eq_, ok_


class GoogleAnalyticsMarkupTests(DxrInstanceTestCase):
    def test_autofocus_root(self):
        """Autofocus the query field at the root of each tree but not
        elsewhere."""
        response = self.client().get('/code/source/')
        ok_('RANDOM_KEY_$#$' in response.data)
        ok_( '.google-analytics.com' in response.data )

