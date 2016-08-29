# -*- coding: UTF-8 -*-

from dxr.testing import DxrInstanceTestCase
from dxr.testing import SingleFileTestCase


class NonAsciiPathTest(DxrInstanceTestCase):
    """Just tests that the index can be created without error."""

    def test_indexes(self):
        pass


class NonAsciiSearchStringTest(SingleFileTestCase):
    source = u"""
        dünya
        """

    def test_unicode(self):
        """Typing some Unicode and hitting Return shouldn't crash."""
        self.single_result_eq(u'dünya', 2)
