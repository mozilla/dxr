from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class TypeTests(SingleFileTestCase):
    source = r"""
        class Foo {};
        class Bar {};
        """ + MINIMAL_MAIN

    def test_simple_type(self):
        self.found_line_eq('type:Foo',
                           'class <b>Foo</b> {};')
        self.found_line_eq('type:Bar',
                           'class <b>Bar</b> {};')

    def test_two_terms(self):
        # There's no type that matches both of these conditions
        self.found_nothing('type:*Foo* type:*Quux*')


class InjectedTypeTests(SingleFileTestCase):
    source = r"""
        template <typename T>
        class Foo {
            void bar(const Foo &);
        };
        """ + MINIMAL_MAIN

    def test_injected_type(self):
        self.found_line_eq('type-ref:Foo', 'void bar(const <b>Foo</b> &amp;);')
