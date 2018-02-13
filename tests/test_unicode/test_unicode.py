# -*- coding: utf-8 -*-

from distutils.dir_util import copy_tree

from dxr.testing import GenerativeTestCase, SingleFileTestCase

class NonAsciiPathTest(GenerativeTestCase):
    """Just tests that the index can be created without error."""

    @classmethod
    def generate(cls):
        """Copy the whole tree to a temp dir so it's on a Linux FS which
        accepts random bags of bytes as filenames.

        macOS (hosting a folder shared through to the Docker container) throws
        a fit on indexing because HFS+ won't put up with the
        non-UTF-8-interpretable names made by the makefile.

        """
        super(NonAsciiPathTest, cls).generate()
        copy_tree(cls.this_dir(), cls._config_dir_path)

    def test_indexes(self):
        pass


class NonAsciiSearchStringTest(SingleFileTestCase):
    source = u"""
        dünya
        """

    def test_unicode(self):
        """Typing some Unicode and hitting Return shouldn't crash."""
        self.single_result_eq(u'dünya', 2)
