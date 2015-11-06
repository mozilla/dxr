from dxr.plugins.clang.tests import CSingleFileTestCase, MINIMAL_MAIN


class TypedefTests(CSingleFileTestCase):
    source = r"""
        typedef int MyTypedef;

        void my_typedef_function(MyTypedef) {
        }
        """ + MINIMAL_MAIN

    def test_typedefs(self):
        self.found_line_eq('+type:MyTypedef',
                           'typedef int <b>MyTypedef</b>;')
        self.found_line_eq('+type-ref:MyTypedef',
                           'void my_typedef_function(<b>MyTypedef</b>) {')
