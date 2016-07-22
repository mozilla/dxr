"""Tests for function searches involving wildcards (*, ?)"""

# Skip tests whose functionality isn't implemented on the es branch yet. Unskip
# before merging to master.
from nose import SkipTest
raise SkipTest

from dxr.plugins.clang.tests import CSingleFileTestCase


class WildcardTests(CSingleFileTestCase):
    source = r"""
        int get_foo() {
            return 0;
        }

        int get_bar() {
            return 0;
        }

        int getX() {
            return 0;
        }

        int main() {
          return get_foo() + get_bar() + getX();
        }
        """

    def test_function_asterisk(self):
        """Test searching for functions using an asterisk."""
        self.found_lines_eq(
            'function:get*',
            [('int <b>get_foo</b>() {', 2),
             ('int <b>get_bar</b>() {', 6),
             ('int <b>getX</b>() {', 10)])

    def test_function_question(self):
        """Test searching for functions using a question mark."""
        self.found_line_eq('function:get_fo?', 'int <b>get_foo</b>() {')

    def test_function_underscore(self):
        """Test that underscore is treated literally when searching for
        functions."""
        self.found_nothing('function:get_')

    def test_function_ref_asterisk(self):
        """Test searching for function references using an asterisk."""
        self.found_line_eq(
            'function-ref:get*',
            'return <b>get_foo</b>() + <b>get_bar</b>() + <b>getX</b>();')

    def test_function_ref_question(self):
        """Test searching for function references using a question mark."""
        self.found_line_eq(
            'function-ref:get_fo?',
            'return <b>get_foo</b>() + get_bar() + getX();')

    def test_function_ref_underscore(self):
        """Test that underscore is treated literally when searching for
        function references."""
        self.found_nothing('function-ref:get_')
