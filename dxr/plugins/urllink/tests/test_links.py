"""Tests for whether urllink finds and links URLs"""

from dxr.testing import SingleFileTestCase, menu_on, MINIMAL_MAIN


class LinkTests(SingleFileTestCase):
    source = r"""
        // Here's a link: http://www.example.com/
        """ + MINIMAL_MAIN

    @classmethod
    def config_input(cls, config_dir_path):
        config = super(LinkTests, cls).config_input(config_dir_path)
        config['DXR']['enabled_plugins'] += ' urllink'
        return config

    def test_one_link(self):
        """Make sure the simple case works."""
        markup = self.source_page('main.cpp')

        menu_on(markup,
                'http://www.example.com/',
                {'html': 'Follow link',
                 'href': 'http://www.example.com/'})
