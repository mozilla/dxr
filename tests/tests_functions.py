"""Tests for searches about functions"""

from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class ReferenceTests(SingleFileTestCase):
    """Tests for finding out where functions are referenced or declared"""

    source = r"""
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

    def test_callers(self):
        """Test that we can find calling functions of another function."""
        self.found_line_eq(
            'callers:getHello', 8, 'int <b>main</b>(int argc, char* argv[]) {')

    def test_called_by(self):
        """Test that we can find the functions a function calls."""
        self.found_line_eq(
            'called-by:main', 4, 'const char* <b>getHello</b>() {')


class ConstTests(SingleFileTestCase):
    source = """
        class ConstOverload
        {
            public:
                void foo();
                void foo() const;
        };

        void ConstOverload::foo() {
        }

        void ConstOverload::foo() const {
        }
        """ + MINIMAL_MAIN

    def test_const_functions(self):
        """Make sure const functions are indexed separately from non-const but
        otherwise identical signatures."""
        self.found_line_eq('+function:ConstOverload::foo()',
                           9,
                           'void ConstOverload::<b>foo</b>() {')
        self.found_line_eq('+function:"ConstOverload::foo() const"',
                            12,
                            'void ConstOverload::<b>foo</b>() const {')
