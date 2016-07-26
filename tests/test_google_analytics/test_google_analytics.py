"""Tests for google analytics snippets"""

from dxr.testing import DxrInstanceTestCase

from nose.tools import ok_


class GoogleAnalyticsMarkupTests(DxrInstanceTestCase):
    def test_google_analytics_snippet_exists(self):
        """Make sure google analytics snippet does show up"""
        response = self.client().get('/code/source/')
        ok_('RANDOM_KEY_$#$' in response.data)
        ok_('.google-analytics.com' in response.data )
