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
                           '<b>Foo</b>&lt;int&gt;();', 8)

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
                           'class Bar : public <b>Foo</b>&lt;T&gt;', 7)
