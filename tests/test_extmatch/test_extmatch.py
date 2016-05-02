"""Tests for the extmatch plugin"""

from os.path import basename

from dxr.testing import DxrInstanceTestCase

from nose.tools import ok_

HEADER = 'Header'
IMPLEMENTATION = 'Implementation'

class ExtmatchTests(DxrInstanceTestCase):

    def test_matches(self):
        def test_match(p, title, match_p, icon_class):
            """Test that the source at path p has a link titled 'title' to
            match_p."""
            markup = self.source_page(p)
            match_base = basename(match_p)
            ok_('<h4>%s</h4>' % title in markup)
            ok_('source/%s" title="%s" class="%s icon">%s</a>' %
                (match_p, match_base, icon_class, match_base) in markup)

        test_match('main.h',
                   IMPLEMENTATION, 'main.cpp', 'cpp')
        test_match('main.cpp',
                   HEADER, 'main.h', 'h')
        test_match('subfolder/main.hxx',
                   IMPLEMENTATION, 'subfolder/main.cxx', 'cpp')
        test_match('subfolder/main.cxx',
                   HEADER, 'subfolder/main.hxx', 'h')
