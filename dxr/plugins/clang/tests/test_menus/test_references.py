"""Tests about whether the searches linked to by context menu items actually
work

"""
from dxr.testing import DxrInstanceTestCase


class ReferenceTests(DxrInstanceTestCase):
    def test_function(self):
        self.found_lines_eq(
                'function-ref:foo',
                [('Space::<b>foo</b>();', 7), ('Bar::<b>foo</b>();', 8)])

    def test_classes(self):
        """Make sure we can find classes.

        Typedefs are covered in type_typedefs.

        """
        self.found_line_eq(
                'type-ref:numba path:main.cpp',
                '<b>numba</b> a = another_file();',
                4)
        self.found_line_eq('type-ref:MyClass', '<b>MyClass</b> c;', 5)
