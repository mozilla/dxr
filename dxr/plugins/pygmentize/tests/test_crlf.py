from nose.tools import ok_

from dxr.testing import SingleFileTestCase

class PygmentizeCRLFTest(SingleFileTestCase):
    """Test that CRLF line endings don't confuse Pygmentize in C preprocessor lines"""

    source_filename = 'main.cpp'
    source = \
        '#include "header.h"\r\n' + \
        '#define MY_MACRO 42\r\n'

    @classmethod
    def config_input(cls, config_dir_path):
        input = super(SingleFileTestCase, cls).config_input(config_dir_path)
        input['DXR']['enabled_plugins'] = 'pygmentize'
        return input

    def test_include(self):
        client = self.client()
        response = client.get('/code/source/main.cpp')
        ok_('<span class="p">\n</span>' not in response.data)
        ok_('<span class="p">include</span> "header.h"\r\n</code>' in response.data)

    def test_define(self):
        client = self.client()
        response = client.get('/code/source/main.cpp')
        ok_('<span class="p">define MY_MACRO 42</span>\r\n</code>' in response.data)
