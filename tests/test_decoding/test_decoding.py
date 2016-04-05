"""Test that we decode files not encoded in source_encoding."""

from dxr.testing import DxrInstanceTestCaseMakeFirst

from nose.tools import ok_


class DecodingTests(DxrInstanceTestCaseMakeFirst):
    def test_utf16_decoding(self):
        """Test that we recognize a utf-16 encoded file as text and that we
        decode and display it properly."""
        markup = self.source_page('utf_16.txt')
        # We only display /source/ lines for files we're able to decode:
        ok_('pandas, bamboo, roly poly' in markup)

    def test_rev_decoding(self):
        """Test that we're decoding as expected on /rev/"""
        response = self.client().get(
            '/code/rev/84eb0ed1a7659d9742a5668402be50d79a0e9764/utf_16.txt')
        ok_('pandas, bamboo, roly poly' in response.data)
