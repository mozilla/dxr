"""Tests for 'Jump to definition' context menu functionality"""

from dxr.testing import DxrInstanceTestCase


class JumpToDefTests(DxrInstanceTestCase):

    def test_redirect_to_def(self):
        """Test that the redirect URL returned from a "Jump to definition"-type
        query finds the definition and doesn't contain any querystring."""
        self.redirect_result_eq('+function:"foo::bar(int, int)"', 'foo.cpp', 3,
                                'single')
        self.redirect_result_eq('+function:baz(int)', 'main.cpp', 3, 'single')
