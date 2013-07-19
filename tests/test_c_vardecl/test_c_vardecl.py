from dxr.testing import DxrInstanceTestCase


class CVarDeclTests(DxrInstanceTestCase):
    """Tests matching up C global variables"""

    def test_decl(self):
        """Search for C variable declaration."""
        self.found_line_eq('var-decl:global', u'extern int <b>global</b>;', 5)

    def test_defn(self):
        """Search for C variable definition."""
        self.found_line_eq('var:global', u'int <b>global</b>;', 3)
