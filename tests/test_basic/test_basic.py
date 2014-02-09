from dxr.testing import DxrInstanceTestCase

from nose.tools import eq_, ok_


class BasicTests(DxrInstanceTestCase):
    """Tests for functionality that isn't specific to particular filters"""

    def test_text(self):
        """Assert that a plain text search works."""
        self.found_files_eq('main', ['main.c', 'makefile'])

    def test_case_sensitive(self):
        """Make sure case-sensitive searching is case-sensitive.

        This tests trilite's substr-extents query type.

        """
        self.found_files_eq('really',
                            ['README.mkd'],
                            is_case_sensitive=True)
        self.found_nothing('REALLY',
                           is_case_sensitive=True)

    def test_case_insensitive(self):
        """Test case-insensitive free-text searching without extents.

        This tests trilite's isubstr query type.

        """
        found_paths = self.found_files(
            '-MAIN', is_case_sensitive=False)
        ok_('main.c' not in found_paths)
        ok_('makefile' not in found_paths)

    def test_case_insensitive_extents(self):
        """Test case-insensitive free-text searching with extents.

        This tests trilite's isubstr-extents query type.

        """
        self.found_files_eq('MAIN',
                            ['main.c', 'makefile'],
                            is_case_sensitive=False)

    def test_index(self):
        """Make sure the index controller redirects."""
        response = self.client().get('/')
        eq_(response.status_code, 302)
        ok_(response.headers['Location'].endswith('/code/source/'))
