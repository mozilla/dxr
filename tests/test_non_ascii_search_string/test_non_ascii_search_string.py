# -*- coding: UTF-8 -*-

from dxr.testing import SingleFileTestCase


class NonAsciiSearchStringTests(SingleFileTestCase):
    source = u"""
        dünya
        """

    def test_unicode(self):
        """Typing some Unicode and hitting Return shouldn't crash."""
        self.single_result_eq(u'dünya', 2)
