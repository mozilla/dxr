"""Tests for contextual menu building"""

from nose.tools import ok_

from dxr.testing import DxrInstanceTestCase


class MenuTests(DxrInstanceTestCase):
    def test_includes(self):
        """Make sure #include cross references are linked."""
        response = self.client().get('/code/source/main.cpp')
        ok_('&quot;href&quot;: &quot;/code/source/extern.c&quot;' in response.data)
