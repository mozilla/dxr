from dxr.testing import DxrInstanceTestCase
from nose.tools import ok_

class BinaryFileTests(DxrInstanceTestCase):
    """Tests that we show something for binary files like images."""

    def test_png(self):
        """Make sure we show a preview of the png."""
        response = self.client().get('/code/source/red_circle.png')
        ok_('src="/code/raw/red_circle.png"' in response.data)
        response = self.client().get('/code/raw/red_circle.png')
        ok_(response.status_code, 200)

    def test_jpeg(self):
        """Make sure we show a preview of the jpeg."""
        response = self.client().get('/code/source/small_blue_circle.jpeg')
        ok_('src="/code/raw/small_blue_circle.jpeg"' in response.data)
        response = self.client().get('/code/raw/small_blue_circle.jpeg')
        ok_(response.status_code, 200)

    def test_jpg(self):
        """Make sure we show a preview of the jpg."""
        response = self.client().get('/code/source/Green circle.jpg')
        ok_('src="/code/raw/Green%20circle.jpg"' in response.data)
        response = self.client().get('/code/raw/Green circle.jpg')
        ok_(response.status_code, 200)

    def test_too_fat(self):
        """Make sure we don't show the preview icon for a file that's too big."""
        response = self.client().get('/code/source/')
        ok_('href="/code/source/Green%20circle.jpg" class="icon image too_fat"' in response.data)

    def test_svg(self):
        """Make sure we show the svg."""
        response = self.client().get('/code/source/yellow_circle.svg')
        ok_('src="/code/raw/yellow_circle.svg"' in response.data)
        response = self.client().get('/code/raw/yellow_circle.svg')
        ok_(response.status_code, 200)

    def test_some_bytes(self):
        """We want some_bytes to show in the folder index, but without its own page."""
        response = self.client().get('/code/source/')
        ok_('some_bytes' in response.data)
        response = self.client().get('/code/source/some_bytes')
        ok_(response.status_code, 404)

    def test_some_bytes(self):
        """We want some_bytes to show on search page, but not be clickable."""
        response = self.client().get('/code/search?q=path%3Asome_bytes&redirect=true')
        ok_('some_bytes' in response.data)
        ok_('href="/code/source/some_bytes"' not in response.data)

