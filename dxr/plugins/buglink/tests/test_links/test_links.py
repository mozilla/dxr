"""Tests for whether buglink finds and links bug references"""

from dxr.testing import DxrInstanceTestCase, menu_on


class LinkTests(DxrInstanceTestCase):
    def test_links(self):
        markup = self.source_page('foo.txt')

        # A bug in the middle of a line:
        menu_on(markup,
                'Bug 123456',
                {'html': 'Bug 123456',
                 'href': 'http://bugs.example.com/123456'})

        # Bugs at the beginning and end of a line. Also, 2 bugs on 1 line:
        menu_on(markup,
                'bug 654321',
                {'html': 'Bug 654321',
                 'href': 'http://bugs.example.com/654321'})
        menu_on(markup,
                'bug 789',
                {'html': 'Bug 789',
                 'href': 'http://bugs.example.com/789'})
