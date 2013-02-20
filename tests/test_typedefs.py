from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class TypedefTests(SingleFileTestCase):
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
