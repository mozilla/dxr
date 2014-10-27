from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class VarTests(SingleFileTestCase):
    source = r"""
        int global;
        int decoy;

        void smoo(int i, char **c) {
            int inner;
        }
        """ + MINIMAL_MAIN

    def test_unqualified(self):
        """Search for var definitions using unqualified names."""
        self.found_line_eq('var:global', u'int <b>global</b>;')

    def test_qualified(self):
        """Search using qualified names in a function scope."""
        self.found_line_eq('+var:"smoo(int, char **)::inner"', u'int <b>inner</b>;')
