from dxr.plugins.clang.tests import CSingleFileTestCase


class OverloadedOperatorTests(CSingleFileTestCase):
    source = """
        struct Foo
        {
            void operator++() {}
            void operator++(int) {}
            void operator+(int) {}
        };

        int main()
        {
            Foo foo;
            ++foo;
            foo++;
            foo + 1;
            return 0;
        }
        """

    def test_preincrement(self):
        self.found_line_eq('+function-ref:Foo::operator++()',
            '<b>++</b>foo;')

    def test_postincrement(self):
        self.found_line_eq('+function-ref:Foo::operator++(int)',
            'foo<b>++</b>;')

    def test_addition(self):
        self.found_line_eq('+function-ref:Foo::operator+(int)',
            'foo <b>+</b> 1;')


class OverloadedOperatorExplicitCallTests(CSingleFileTestCase):
    source = """
        struct Foo
        {
            void operator++() {}
            void operator++(int) {}
            void operator+(int) {}
        };

        int main()
        {
            Foo foo;
            foo.operator++();
            foo.operator++(1);
            foo.operator+(1);
            return 0;
        }
        """

    def test_preincrement(self):
        self.found_line_eq('+function-ref:Foo::operator++()',
            'foo.<b>operator++</b>();')

    def test_postincrement(self):
        self.found_line_eq('+function-ref:Foo::operator++(int)',
            'foo.<b>operator++</b>(1);')

    def test_addition(self):
        self.found_line_eq('+function-ref:Foo::operator+(int)',
            'foo.<b>operator+</b>(1);')

