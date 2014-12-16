from dxr.testing import SingleFileTestCase


class OperatorCallTests(SingleFileTestCase):
    source = """
        struct Foo
        {
                void operator()(int)
                {
                }
                void operator[](int)
                {
                }
        };

        int main()
        {
            Foo foo;
            int alpha = 0;
            foo(alpha);
            int beta = 0;
            foo[beta];
            return 0;
        }
        """

    def test_operator_call(self):
        self.found_line_eq('+function-ref:Foo::operator()(int)',
            'foo<b>(</b>alpha);')

    def test_call_argument(self):
        self.found_line_eq('+var-ref:main()::alpha',
            'foo(<b>alpha</b>);')

    def test_operator_subscript(self):
        self.found_line_eq('+function-ref:Foo::operator[](int)',
            'foo<b>[</b>beta];')

    def test_subscript_argument(self):
        self.found_line_eq('+var-ref:main()::beta',
            'foo[<b>beta</b>];')


class ExplicitOperatorCallTests(SingleFileTestCase):
    source = """
        struct Foo
        {
                void operator()(int)
                {
                }
                void operator[](int)
                {
                }
        };

        int main()
        {
            Foo foo;
            int alpha = 0;
            foo.operator()(alpha);
            int beta = 0;
            foo.operator[](beta);
            return 0;
        }
        """

    def test_operator_call(self):
        self.found_line_eq('+function-ref:Foo::operator()(int)',
            'foo.<b>operator()</b>(alpha);')

    def test_call_argument(self):
        self.found_line_eq('+var-ref:main()::alpha',
            'foo.operator()(<b>alpha</b>);')

    def test_operator_subscript(self):
        self.found_line_eq('+function-ref:Foo::operator[](int)',
            'foo.<b>operator[]</b>(beta);')

    def test_subscript_argument(self):
        self.found_line_eq('+var-ref:main()::beta',
            'foo.operator[](<b>beta</b>);')
