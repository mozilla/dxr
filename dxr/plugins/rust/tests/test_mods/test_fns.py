"""These tests are testing references involving modules, as opposed to modules themselves.
   All the tests are on funtions, but I believe any other item will be similar."""

from dxr.testing import DxrInstanceTestCase

class ModFnTests(DxrInstanceTestCase):
    def test_fn_def(self):
        self.found_line_eq('function:foo', "pub fn <b>foo</b>() {}", 19)
        self.found_lines_eq('function:bar',
                            [('pub fn <b>bar</b>() {}', 6),
                             ('pub fn <b>bar</b>() {}', 11)])

    def test_fn_def_qual(self):
        self.found_line_eq('+function:test::mod2::foo', "pub fn <b>foo</b>() {}", 19)
        self.found_line_eq('+function:test::mod1::mod11::mod111::bar', "pub fn <b>bar</b>() {}", 6)
        self.found_line_eq('+function:test::mod1::mod12::bar', "pub fn <b>bar</b>() {}", 11)

    def test_fn_ref(self):
        self.found_line_eq('function-ref:foo', "mod2::<b>foo</b>();", 26)
        self.found_lines_eq('function-ref:bar',
                            [('pub use mod1::mod12::<b>bar</b>;', 18),
                             ('::mod1::mod11::mod111::<b>bar</b>();', 25),
                             ('mod2::<b>bar</b>();', 27),
                             ('mod111::<b>bar</b>();', 33),
                             ('moda::<b>bar</b>();', 34),
                             ('<b>bar</b>();', 40),
                             ('mod11::mod111::<b>bar</b>();', 46),
                             ('mod12::<b>bar</b>();', 47),
                             ('use mod1::mod12::<b>bar</b>;', 51),
                             ('<b>bar</b>();', 53),
                             ('use mod1::mod12::<b>bar</b> as baz;', 57),
                             ('<b>baz</b>();', 59),
                             ('use mod1::mod12::{self, <b>bar</b>};', 63),
                             ('<b>bar</b>();', 65),
                             ('mod12::<b>bar</b>();', 66)])

    def test_fn_ref_qual(self):
        self.found_line_eq('+function-ref:test::mod2::foo', "mod2::<b>foo</b>();", 26)
        self.found_lines_eq('+function-ref:test::mod1::mod11::mod111::bar',
                            [('::mod1::mod11::mod111::<b>bar</b>();', 25),
                             ('mod111::<b>bar</b>();', 33),
                             ('moda::<b>bar</b>();', 34),
                             ('mod11::mod111::<b>bar</b>();', 46)])
        self.found_lines_eq('+function-ref:test::mod1::mod12::bar',
                            [('pub use mod1::mod12::<b>bar</b>;', 18),
                             ('mod2::<b>bar</b>();', 27),
                             ('<b>bar</b>();', 40),
                             ('mod12::<b>bar</b>();', 47),
                             ('use mod1::mod12::<b>bar</b>;', 51),
                             ('<b>bar</b>();', 53),
                             ('use mod1::mod12::<b>bar</b> as baz;', 57),
                             ('<b>baz</b>();', 59),
                             ('use mod1::mod12::{self, <b>bar</b>};', 63),
                             ('<b>bar</b>();', 65),
                             ('mod12::<b>bar</b>();', 66)])
