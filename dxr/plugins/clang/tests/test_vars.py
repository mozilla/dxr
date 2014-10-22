from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class VarTests(SingleFileTestCase):
    source = r"""
        int global;
        int decoy;
        """ + MINIMAL_MAIN

    def test_defn(self):
        """Search for C variable definition."""
        self.found_line_eq('var:global', u'int <b>global</b>;')
