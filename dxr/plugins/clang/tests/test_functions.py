"""Tests for searches about functions"""

# Skip tests whose functionality isn't implemented on the es branch yet. Unskip
# before merging to master.
from nose import SkipTest
raise SkipTest

from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class DefinitionTests(SingleFileTestCase):
    """Tests for finding where functions are defined"""

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

    def test_definition(self):
        """Try searching for function declarations."""
        self.found_line_eq(
            'function:main', 'int <b>main</b>(int argc, char* argv[]) {')
        self.found_line_eq(
            'function:getHello', 'const char* <b>getHello</b>() {')


class TemplateClassMemberReferenceTests(SingleFileTestCase):
    """Tests for finding out where member functions of a template class are referenced or declared"""

    source = r"""
        template <typename T>
        class Foo
        {
        public:
            void bar();
        };

        template <typename T>
        void Foo<T>::bar()
        {
        }

        void baz()
        {
            Foo<int>().bar();
        }
        """ + MINIMAL_MAIN

    def test_function_decl(self):
        """Try searching for function declaration."""
        self.found_line_eq('+function-decl:Foo::bar()', 'void <b>bar</b>();')

    def test_function(self):
        """Try searching for function definition."""
        self.found_lines_eq('+function:Foo::bar()',
                            [('void Foo&lt;T&gt;::<b>bar</b>()', 10)])

    def test_function_ref(self):
        """Try searching for function references."""
        self.found_lines_eq('+function-ref:Foo::bar()',
                            [('Foo&lt;int&gt;().<b>bar</b>();', 16)])


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
