"""Tests about whether the searches linked to by context menu items actually
work

"""
from dxr.testing import DxrInstanceTestCase


class ReferenceTests(DxrInstanceTestCase):
    """Any reference searches not tested here are tested elsewhere."""

    def test_function(self):
        self.found_lines_eq(
                'function-ref:foo',
                [('Space::<b>foo</b>();', 10), ('Bar::<b>foo</b>();', 11)])

    def test_classes(self):
        """Make sure we can find classes.

        Typedefs are covered in type_typedefs.

        """
        self.found_line_eq(
                'type-ref:numba path:main.cpp',
                '<b>numba</b> a = another_file();',
                6)
        self.found_line_eq('type-ref:MyClass path:main.cpp', '<b>MyClass</b> c;', 7)

    def test_var(self):
        """Test var-refs.

        Plain old var: queries are covered in test_c_vardecl.

        """
        self.found_line_eq('var-ref:var', 'return <b>var</b>;', 15)
