"""A big bag of small tests

When there get to be too many, we'll split them out into smaller files.

"""
from dxr.testing import SingleFileTestCase


class ReferenceTests(SingleFileTestCase):
    """Tests for finding out where various things are referenced or declared"""

    source = ur"""
        #include <stdio.h>

        const char* getHello() {
            return "Hello World";
        }

        int main(int argc, char* argv[]) {
          printf("%s\n", getHello());
          return 0;
        }
        """

    def test_functions(self):
        """Try searching for function declarations."""
        self.found_line_eq(
            'function:main', 8, 'int <b>main</b>(int argc, char* argv[]) {')
        self.found_line_eq(
            'function:getHello', 4, 'const char* <b>getHello</b>() {')
