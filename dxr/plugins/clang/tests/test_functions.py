"""Tests for searches about functions"""

from nose import SkipTest

from dxr.plugins.clang.tests import CSingleFileTestCase, MINIMAL_MAIN


class DefinitionTests(CSingleFileTestCase):
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

        namespace Space {
          void foo(int a) {}
        }
        """

    def test_names(self):
        """Try searching for function names case-sensitively."""
        self.found_line_eq('function:@main', 'int <b>main</b>(int argc, char* argv[]) {')
        self.found_line_eq('function:getHello', 'const char* <b>getHello</b>() {')
        self.found_nothing('function:getHELLO')

    def test_names_caseless(self):
        """Try searching for function names case-insensitively."""
        self.found_line_eq(
            'function:main',
            'int <b>main</b>(int argc, char* argv[]) {')

    def test_qualnames_unqualified(self):
        """Qualnames should be found when searching unqualified as well."""
        self.found_line_eq(
            'function:Space::foo(int)', 'void <b>foo</b>(int a) {}')

    def test_scoped(self):
        """Functions with explicit scopes should be found even when types are
        left off."""
        self.found_line_eq(
            'function:Space::foo', 'void <b>foo</b>(int a) {}')

    def test_qualnames_caseless(self):
        """Case-insensitive qualified searches should remain case-sensitive.

        I guess. This is really more of a marker to show that I knew about
        this behavior and didn't expressly condemn it.

        """
        self.found_nothing('+function:SPACE::FOO(int)')


class TemplateClassMemberReferenceTests(CSingleFileTestCase):
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
        raise SkipTest('The template params ("<int>") get into the qualified name. We do not want them in there; we want to search out all uses of the function, regardless of parametrization.')
        self.found_lines_eq('+function-ref:Foo::bar()',
                            [('Foo&lt;int&gt;().<b>bar</b>();', 16)])


class TemplateMemberReferenceTests(CSingleFileTestCase):
    """Tests for finding out where template member functions of a class are referenced or declared"""

    source = r"""
        class Foo
        {
        public:
            template <typename T>
            void bar();
        };

        template <typename T>
        void Foo::bar()
        {
        }

        void baz()
        {
            Foo().bar<int>();
        }
        """ + MINIMAL_MAIN

    def test_function_decl(self):
        """Try searching for function declaration."""
        self.found_line_eq('+function-decl:Foo::bar()', 'void <b>bar</b>();')

    def test_function(self):
        """Try searching for function definition."""
        self.found_lines_eq('+function:Foo::bar()',
                            [('void Foo::<b>bar</b>()', 10)])

    def test_function_ref(self):
        """Try searching for function references."""
        self.found_lines_eq('+function-ref:Foo::bar()',
                            [('Foo().<b>bar</b>&lt;int&gt;();', 16)])


class ConstTests(CSingleFileTestCase):
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


class PrototypeParamTests(CSingleFileTestCase):
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
