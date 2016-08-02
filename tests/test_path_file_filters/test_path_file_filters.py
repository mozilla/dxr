# -*- coding: utf-8 -*-

from nose import SkipTest
from nose.tools import raises

from dxr.testing import DxrInstanceTestCase


class PathAndFileFilterTests(DxrInstanceTestCase):
    """Basic tests for functionality of the 'path:' and 'file:' filters"""

    def test_basic_path_results(self):
        """Check that a 'path:' result includes both file and folder matches."""
        self.found_files_eq('path:fish', ['fish1', 'fishy_folder/fish2',
                                          'fishy_folder/gill', 'folder/fish3',
                                          'folder/fish4'])

    def test_basic_file_results(self):
        """Check that a 'file:' result includes only file matches."""
        self.found_files_eq('file:fish', ['fish1', 'fishy_folder/fish2',
                                          'folder/fish3', 'folder/fish4'])

    def test_path_and_file_line_promotion(self):
        """Make sure promotion of a 'path:' or 'file:' filter to a LINE query
        works.

        """
        self.found_files_eq('path:fish fins', ['folder/fish3'])
        self.found_files_eq('file:fish fins', ['folder/fish3'])

    # This fails because we currently intentionally exclude folder paths from
    # FILE query results - remove the @raises line when that's changed.  (Of
    # course then other tests here will need to be updated as well.)
    @raises(AssertionError)
    def test_empty_folder_path_results(self):
        """Check that 'path:' results include empty folders."""
        self.found_files_eq('path:empty_folder', ['empty_folder'])

    def test_basic_wildcard(self):
        """Test basic wildcard functionality."""
        # 'path:' and 'file:' currently have the same underlying wildcard
        # support, so we're spreading out the basic wildcard testing over both.
        self.found_files_eq('path:fish?_fo*er',
                            ['fishy_folder/fish2', 'fishy_folder/gill'])

        self.found_files_eq('file:fish[14]', ['fish1', 'folder/fish4'])

    def test_unicode(self):
        """Make sure searching for non-ASCII names works."""
        raise SkipTest('This test fails on Travis but passes locally. It may '
                       'be because of an LC_ALL difference.')
        self.found_files_eq(u'file:fre\u0301mium*', [u'fre\u0301mium.txt'])

        # This one fails locally, perhaps because é is normalized differently
        # in ES than here. See bug 1291471.
        # self.found_files_eq(u'file:frémium*', [u'frémium.txt'])
