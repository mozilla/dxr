from dxr.testing import DxrInstanceTestCase
from nose.tools import ok_

class BinaryFileTests(DxrInstanceTestCase):
    """Tests that we show something for binary files like images."""
    def test_png(self):
        '''
        Make sure we show a preview of the png.
        '''
        response = self.client().get('/code/source/red_circle.png')
        ok_('<img src="/code/images/red_circle.png">' in response.data)
        response = self.client().get('/code/images/red_circle.png')
        ok_(response.status_code, 200)

    def test_jpeg(self):
        '''
        Make sure we show a preview of the jpeg.
        '''
        response = self.client().get('/code/source/small_blue_circle.jpeg')
        ok_('<img src="/code/images/small_blue_circle.jpeg">' in response.data)
        response = self.client().get('/code/images/small_blue_circle.jpeg')
        ok_(response.status_code, 200)

    def test_jpg(self):
        '''
        Make sure we show a preview of the jpg.
        '''
        response = self.client().get('/code/source/Green circle.jpg')
        ok_('<img src="/code/images/Green circle.jpg">' in response.data)
        response = self.client().get('/code/images/Green circle.jpg')
        ok_(response.status_code, 200)

    def test_svg(self):
        '''
        Make sure we show a preview of the svg as well as its code.
        '''
        response = self.client().get('/code/source/yellow_circle.svg')
        ok_('<img src="/code/images/yellow_circle.svg">' in response.data)
        ok_('xmlns:svg="http://www.w3.org/2000/svg"' in response.data)
        response = self.client().get('/code/images/yellow_circle.svg')
        ok_(response.status_code, 200)

    def test_some_bytes(self):
        '''
        We can just say "binary file" for some_bytes
        '''
        response = self.client().get('/code/source/some_bytes')
        ok_('(binary file)' in response.data)
