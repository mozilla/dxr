from dxr.testing import DxrInstanceTestCase


class FileExtensionsTests(DxrInstanceTestCase):
    """Tests searching for files by extension"""

    def test_extensions(self):
        """Try search by filename extension."""
        self.found_files_eq('ext:c', ['main.c', 'dot_c.c'])
        self.found_files_eq('ext:cpp', ['hello-world.cpp'])
        self.found_files_eq('ext:inc', ['hello-world.inc'])

    def test_extensions_formatting(self):
        """Extensions can be preceeded by a dot"""
        self.found_files_eq('ext:.c', ['main.c', 'dot_c.c'])

    def test_union_only(self):
        """Make sure that multiple ext filters are joined with 'or' instead of 'and.'"""
        self.found_files_eq('ext:c ext:cpp', ['main.c', 'dot_c.c', 'hello-world.cpp'])
