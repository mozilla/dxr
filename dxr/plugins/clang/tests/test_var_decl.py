from dxr.testing import menu_on
from dxr.plugins.clang.tests import CSingleFileTestCase


class VarDeclTests(CSingleFileTestCase):
    source = r"""
        extern int Default;

        int Default = 42;

        int getDefault()
        {
            return Default;
        }
        """

    def test_menu(self):
        """Menu can search for declarations and references."""
        menu_on(self.source_page(self.source_filename),
                'Default',
                {'html': 'Find declarations',
                 'href': '/code/search?q=%2Bvar-decl%3ADefault'},
                {'html': 'Find references',
                 'href': '/code/search?q=%2Bvar-ref%3ADefault'})
