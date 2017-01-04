# -*- coding: utf-8 -*-

from os.path import basename, join
from shutil import copytree

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
        temp_dir = join(cls._config_dir_path, basename(cls.this_dir()))
        copytree(cls.this_dir(), temp_dir)
        cls._orig_config_dir, cls._config_dir_path = cls._config_dir_path, temp_dir

    @classmethod
    def index(cls):
        cls.dxr_index()

    @classmethod
    def teardown_class(cls):
        """Restore config path so superclass will delete the temp dir made by
        the superclass.

        That dir also contains everything we've copied over.

        """
        cls._config_dir_path = cls._orig_config_dir
        super(NonAsciiPathTest, cls).teardown_class()

    def test_indexes(self):
        pass


class NonAsciiSearchStringTest(SingleFileTestCase):
    source = u"""
        dünya
        """

    def test_unicode(self):
        """Typing some Unicode and hitting Return shouldn't crash."""
        self.single_result_eq(u'dünya', 2)
