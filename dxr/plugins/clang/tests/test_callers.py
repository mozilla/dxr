"""Tests for searches using callers"""

from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class DirectCallTests(SingleFileTestCase):
    """Tests for searches involving direct calls"""

    source = r"""
        void orphan()
        {
        }

        void called_once(int a)
        {
        }

        void called_twice()
        {
        }

        void call_two()
        {
            called_twice();
            called_once(5);
        }

        int main()
        {
            called_twice();
            return 0;
        }
        """

    def test_no_caller(self):
        self.found_nothing('callers:orphan')

    def test_one_caller(self):
        """Make sure that we highlight the entire call, including argument the list."""
        self.found_line_eq('callers:called_once', '<b>called_once(5)</b>;')

    def test_qualified(self):
        self.found_line_eq('+callers:called_once(int)', '<b>called_once(5)</b>;')

    def test_two_callers(self):
        self.found_lines_eq('callers:called_twice', [
            ('<b>called_twice()</b>;', 16),
            ('<b>called_twice()</b>;', 22)])


class IndirectCallTests(SingleFileTestCase):
    """Tests for searches involving indirect (virtual) calls"""

    source = r"""
        class Base
        {
            public:
                Base() {}
                virtual void foo() {}
                void bar() {}
        };

        class Derived : public Base
        {
            public:
                Derived() {}
                virtual void foo() {}
                void bar() {}
        };

        void c1(Base &b)
        {
            b.foo();
            b.bar();
        }

        void c2(Derived &d)
        {
            d.foo();
            d.bar();
        }
        """ + MINIMAL_MAIN

    def test_virtual_base(self):
        """Virtual methods on base classes should be found only on invocations
        against base-class-typed things.

        C++ does not automatically downcast things from base to derived types.

        """
        self.found_line_eq('+callers:Base::foo()', '<b>b.foo()</b>;')

    def test_virtual_derived(self):
        """Make sure derived-class method invocations are found on derived and
        base classes.

        We play it safe with derived methods. We say we found them when
        they're invoked on something with the type of the derived class *or*
        any of its base classes that have such a method. That way, we have, at
        worst, false positives.

        """
        # b could be a Base or a Derived. We have to look to the whole-program
        # analysis pass to tell; C++ happily upcasts.
        self.found_lines_eq('+callers:Derived::foo()', [
            ('<b>b.foo()</b>;', 20),
            ('<b>d.foo()</b>;', 26)])

    def test_non_virtual(self):
        """Non-virtual methods should always resolve according to their ptr types."""
        self.found_line_eq('+callers:Base::bar()', '<b>b.bar()</b>;')
        self.found_line_eq('+callers:Derived::bar()', '<b>d.bar()</b>;')
