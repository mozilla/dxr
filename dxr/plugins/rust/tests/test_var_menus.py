from dxr.plugins.rust.tests import RustSingleFileTestCase
from dxr.testing import menu_on

class VarMenuTests(RustSingleFileTestCase):
    source = """
    fn main() {
        let _ = FOO;
    }
    const FOO: i32 = 42;
    """

    def test_const_link(self):
        """ test that the link to defintion works properly """
        menu_on(self.source_page('mod.rs'),
                'FOO',
                {'html': 'Jump to definition',
                         'href': '/code/source/mod.rs#5'})
