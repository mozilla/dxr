from dxr.testing import DxrInstanceTestCase


class UnionOnlyTests(DxrInstanceTestCase):
    """Test that multiple usages of union_only filters will OR together results."""

    def test_union_only(self):
        # Make sure that multiple ext filters are joined with 'or' instead of 'and.'
        self.found_files_eq('ext:c ext:cpp', ['main.c', 'dot_c.c', 'hello-world.cpp'])
