from dxr.testing import DxrInstanceTestCase


class BasicTests(DxrInstanceTestCase):
    """Tests for functionality that isn't specific to particular filters"""

    def test_text(self):
        """Assert that a plain text search works."""
        self.found_files_eq('main', ['main.c', 'makefile'])

    def test_case_insensitive(self):
        """Test case-insensitive free-text searching.

        This tests trilite's isubstr-extents query type.

        """
        self.found_files_eq('MAIN',
                            ['main.c', 'makefile'],
                            is_case_sensitive=False)

    # TODO: Test isubstr query type as well.
