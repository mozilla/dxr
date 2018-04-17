from dxr.plugins.clang.tests import CSingleFileTestCase


class ThirdPartyRefsTests(CSingleFileTestCase):
    source = """
        #include <string.h>

        void foo(int);

        struct C {
            C(int);
        };

        int main()
        {
            char s[6];
            strcpy(s, "Hello");
            foo(1);
            C c(1);
            return 0;
        }
        """

    def test_ref_libc(self):
        """Search for references to a function that is defined in libc."""
        self.found_line_eq('function-ref:strcpy',
            '<b>strcpy</b>(s, "Hello");')

    def test_ref_not_defined(self):
        """Search for references to a function that is not defined."""
        self.found_line_eq('+function-ref:foo(int)',
            '<b>foo</b>(1);')

    def test_decl_not_defined(self):
        """Search for declarations for a function that is not defined."""
        self.found_line_eq('+function-decl:foo(int)',
            'void <b>foo</b>(int);')

    def test_decl_constructor(self):
        """Search for declarations for a constructor that is not defined."""
        self.found_line_eq('+function-decl:C::C(int)',
            '<b>C</b>(int);')

    def test_call_libc(self):
        """Search for calls to a function that is defined in libc."""
        self.found_line_eq('callers:strcpy',
            '<b>strcpy(s, "Hello")</b>;')

    def test_call_not_defined(self):
        """Search for calls to a function that is not defined."""
        self.found_line_eq('+callers:foo(int)',
            '<b>foo(1)</b>;')

    def test_call_constructor(self):
        """Search for calls to a constructor that is not defined."""
        self.found_line_eq('+callers:C::C(int)',
            'C <b>c(1)</b>;')

