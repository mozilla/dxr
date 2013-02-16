from dxr.testing import DxrInstanceTestCase


class BasicTests(DxrInstanceTestCase):
    """Tests for functionality that isn't specific to particular filters"""

    def test_text(self):
        """Assert that a plain text search works."""
        self.found_files_eq('main', ['main.c', 'makefile'])

    def test_extensions(self):
        """Try search by filename extension."""
        self.found_files_eq('ext:c', ['main.c', 'dot_c.c'])
