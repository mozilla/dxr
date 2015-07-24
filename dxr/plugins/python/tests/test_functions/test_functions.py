from dxr.testing import DxrInstanceTestCase, menu_on

SEARCH = '/code/search?q=%s%%3A%s'


class FunctionDefTests(DxrInstanceTestCase):
    def test_simple_function(self):
        self.found_line_eq('function:foo', "def <b>foo</b>():", 2)

    def test_case_insensitive(self):
        self.found_line_eq('function:FOO', "def <b>foo</b>():", 2,
                           is_case_sensitive=False)

    def test_methods_are_functions_too(self):
        self.found_line_eq('function:baz', "def <b>baz</b>(self):", 13)

    def test_multiple_with_same_name(self):
        self.found_lines_eq('function:bar',
                            [("def <b>bar</b>():", 5),
                             ("def <b>bar</b>(self):", 10)])

    def test_function_ref(self):
        self.found_line_eq('function-ref:bar', "<b>bar</b>()", 3)

    def test_function_caller_menu(self):
        page = self.source_page("main.py")
        menu_on(page, 'bar', {
            'html': 'Find definition',
            'href': SEARCH % ('id', 'bar')
        })

    def test_function_def_menu(self):
        page = self.source_page("main.py")
        menu_on(page, 'foo', {
            'html': 'Find references',
            'href': SEARCH % ('ref', 'foo')
        })
