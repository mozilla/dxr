from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class TypeTests(SingleFileTestCase):
    source = r"""
        template <typename T>
        class Foo
        {
        };
        void bar()
        {
            Foo<int>();
        }
        """ + MINIMAL_MAIN

    def test_simple_type(self):
        self.found_line_eq('type:Foo',
                           'class <b>Foo</b>')
        self.found_line_eq('type-ref:Foo',
                           '<b>Foo</b>&lt;int&gt;();')

class BaseClassTests(SingleFileTestCase):
    source = r"""
        template <typename T>
        class Foo
        {
        };
        template <typename T>
        class Bar : public Foo<T>
        {
        };
        """ + MINIMAL_MAIN

    def test_base_class(self):
        self.found_line_eq('type-ref:Foo',
                           'class Bar : public <b>Foo</b>&lt;T&gt;')

class TemplateParameterTests(SingleFileTestCase):
    source = r"""
        template <typename T>
        class Foo
        {
            Foo(const T &);
        };
        template <typename T>
        void bar(const T &)
        {
        }
        """ + MINIMAL_MAIN

    def test_class_template_parameter(self):
        self.found_line_eq('+type:Foo::T',
                           'template &lt;typename <b>T</b>&gt;', 2)
        self.found_line_eq('+type-ref:Foo::T',
                           'Foo(const <b>T</b> &amp;);')

    def test_function_template_parameter(self):
        self.found_line_eq('+type:"bar(const T &)::T"',
                           'template &lt;typename <b>T</b>&gt;', 7)
        self.found_line_eq('+type-ref:"bar(const T &)::T"',
                           'void bar(const <b>T</b> &amp;)')
