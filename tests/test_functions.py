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
            'function:main', 'int <b>main</b>(int argc, char* argv[]) {')
        self.found_line_eq(
            'function:getHello', 'const char* <b>getHello</b>() {')

    def test_callers(self):
        """Test that we can find calling functions of another function."""
        self.found_line_eq(
            'callers:getHello', 'int <b>main</b>(int argc, char* argv[]) {')

    def test_called_by(self):
        """Test that we can find the functions a function calls."""
        self.found_line_eq(
            'called-by:main', 'const char* <b>getHello</b>() {')


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
                           'void ConstOverload::<b>foo</b>() {')
        self.found_line_eq('+function:"ConstOverload::foo() const"',
                            'void ConstOverload::<b>foo</b>() const {')


class PrototypeParamTests(SingleFileTestCase):
    source = """
        int prototype_parameter_function(int prototype_parameter);

        int prototype_parameter_function(int prototype_parameter) {
            return prototype_parameter;
        }
        """ + MINIMAL_MAIN

    def test_prototype_params(self):
        # I have no idea what this tests.
        self.found_line_eq(
            '+var:prototype_parameter_function(int)::prototype_parameter',
            'int prototype_parameter_function(int <b>prototype_parameter</b>) {')
        self.found_line_eq(
            '+var-ref:prototype_parameter_function(int)::prototype_parameter',
            'return <b>prototype_parameter</b>;')
