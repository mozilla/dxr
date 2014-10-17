"""Tests about whether the searches linked to by context menu items actually
work

"""
from dxr.testing import DxrInstanceTestCase


class ReferenceTests(DxrInstanceTestCase):
    def test_function(self):
        self.found_lines_eq(
                'function-ref:foo',
                [('Space::<b>foo</b>();', 7), ('Bar::<b>foo</b>();', 8)])
