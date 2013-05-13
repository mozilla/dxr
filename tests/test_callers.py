"""Tests for searches using callers and called-by"""

from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class DirectCallTests(SingleFileTestCase):
    """Tests for searches involving direct calls"""

    source = r"""
        void orphan()
        {
        }

        void called_once()
        {
        }

        void called_twice()
        {
        }

        void call_two()
        {
            called_twice();
            called_once();
        }

        int main()
        {
            called_twice();
            return 0;
        }
        """

    def test_no_caller(self):
        self.found_nothing('callers:orphan')

    def test_no_callees(self):
        self.found_nothing('called-by:orphan')

    def test_one_caller(self):
        self.found_line_eq('callers:called_once', 'void <b>call_two</b>()')

    def test_two_callers(self):
        self.found_lines_eq('callers:called_twice', [
            ('void <b>call_two</b>()', 14),
            ('int <b>main</b>()', 20)])

    def test_one_callee(self):
        self.found_line_eq('called-by:main', 'void <b>called_twice</b>()')

    def test_two_callees(self):
        self.found_lines_eq('called-by:call_two', [
            ('void <b>called_once</b>()', 6),
            ('void <b>called_twice</b>()', 10)])


class IndirectCallTests(SingleFileTestCase):
    """Tests for searches involving indirect (virtual) calls"""

    source = r"""
        class Base
        {
        public:
            Base() {}
            virtual void foo() {}
        };

        class Derived : public Base
        {
        public:
            Derived() {}
            virtual void foo() {}
        };

        void c1(Base &b)
        {
            b.foo();
        }

        void c2(Derived &d)
        {
            d.foo();
        }
        """ + MINIMAL_MAIN

    def test_callers(self):
        self.found_lines_eq('+callers:Base::foo()', [
            ('void <b>c1</b>(Base &amp;b)', 16)])
        self.found_lines_eq('+callers:Derived::foo()', [
            ('void <b>c1</b>(Base &amp;b)', 16),
            ('void <b>c2</b>(Derived &amp;d)', 21)])

    def test_callees(self):
        self.found_lines_eq('called-by:c1', [
            ('virtual void <b>foo</b>() {}', 6),
            ('virtual void <b>foo</b>() {}', 13)])
        self.found_lines_eq('called-by:c2', [
            ('virtual void <b>foo</b>() {}', 13)])
