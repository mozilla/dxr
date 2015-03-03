from textwrap import dedent

from dxr.plugins.python.tests import PythonSingleFileTestCase


class CallersTests(PythonSingleFileTestCase):
    source = dedent("""
    def call_once():
        called_once()

    def call_multiple():
        called_multiple()
        called_multiple()

    def call_in_separate_functions_1():
        called_in_separate_functions()

    def call_in_separate_functions_2():
        called_in_separate_functions()

    def outer_call_bar():
        def inner_call_foo():
            foo()
        bar()
    """)

    def test_called_once(self):
        self.found_line_eq('callers:called_once', 'def <b>call_once</b>():')

    def test_called_multiple_times(self):
        self.found_line_eq('callers:called_multiple', 'def <b>call_multiple</b>():')

    def test_called_in_several_functions(self):
        self.found_lines_eq('callers:called_in_separate_functions', [
            'def <b>call_in_separate_functions_1</b>():',
            'def <b>call_in_separate_functions_2</b>():',
        ])

    def test_called_in_inner_function(self):
        """Make sure a call within an inner function matches the inner
        function only.

        """
        self.found_line_eq('callers:foo', 'def <b>inner_call_foo</b>():')

    def test_called_in_outer_function(self):
        """Make sure inner function definitions do not affect other
        calls in the outer function.

        """
        self.found_line_eq('callers:bar', 'def <b>outer_call_bar</b>():')
