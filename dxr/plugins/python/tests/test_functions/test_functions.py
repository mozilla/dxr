from dxr.testing import DxrInstanceTestCase


class FunctionDefTests(DxrInstanceTestCase):
    def test_simple_function(self):
        self.found_line_eq('function:foo', "def <b>foo</b>():", 2)

    def test_methods_are_functions_too(self):
        self.found_line_eq('function:baz', "def <b>baz</b>(self):", 13)

    def test_multiple_with_same_name(self):
        self.found_lines_eq('function:bar',
                            [("def <b>bar</b>():", 5),
                             ("def <b>bar</b>(self):", 10)])
