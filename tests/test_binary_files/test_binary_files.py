from dxr.testing import DxrInstanceTestCase
from nose.tools import ok_, eq_

class BinaryFileTests(DxrInstanceTestCase):
    """Tests that we show something for binary files like images."""

    def test_png(self):
        """Make sure we show a preview of the png."""
        response = self.client().get('/code/source/red_circle.png')
        ok_('src="/code/raw/red_circle.png"' in response.data)
        response = self.client().get('/code/raw/red_circle.png')
        eq_(response.status_code, 200)

    def test_jpeg(self):
        """Make sure we show a preview of the jpeg."""
        response = self.client().get('/code/source/small_blue_circle.jpeg')
        ok_('src="/code/raw/small_blue_circle.jpeg"' in response.data)
        response = self.client().get('/code/raw/small_blue_circle.jpeg')
        eq_(response.status_code, 200)

    def test_jpg(self):
        """Make sure we show a preview of the jpg."""
        response = self.client().get('/code/source/Green circle.jpg')
        ok_('src="/code/raw/Green%20circle.jpg"' in response.data)
        response = self.client().get('/code/raw/Green circle.jpg')
        eq_(response.status_code, 200)

    def test_too_fat(self):
        """Make sure we don't show the preview icon for a file that's too big."""
        response = self.client().get('/code/source/')
        ok_('href="/code/source/Green%20circle.jpg" class="icon image too_fat"' in response.data)

    def test_svg(self):
        """Make sure we show the source of the svg, but allow a way to reach its image."""
        response = self.client().get('/code/source/yellow_circle.svg')
        ok_('href="/code/raw/yellow_circle.svg"' in response.data)
        response = self.client().get('/code/raw/yellow_circle.svg')
        eq_(response.status_code, 200)

    def test_some_bytes_sourceable(self):
        """Make sure some_bytes gets a /source/ page that shows "(binary
        file)"."""
        response = self.client().get('/code/source/some_bytes')
        ok_('(binary file)' in response.data)
