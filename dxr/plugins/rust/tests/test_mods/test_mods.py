from dxr.testing import DxrInstanceTestCase

class ModTests(DxrInstanceTestCase):
    def test_mod_def(self):
        # Test top level module.
        self.found_line_eq('module:mod1', "mod <b>mod1</b> {", 3)
        # Test nested module.
        self.found_line_eq('module:mod111', "pub mod <b>mod111</b> {", 5)
        # Test module name with multiple definitions.
        self.found_lines_eq('module:mod3',
                            [("pub mod <b>mod3</b> {}", 13),
                             ("pub mod <b>mod3</b> {}", 21)])

    def test_mod_def_qual(self):
        self.found_line_eq('+module:test::mod1', "mod <b>mod1</b> {", 3)
        self.found_line_eq('+module:test::mod1::mod11::mod111', "pub mod <b>mod111</b> {", 5)
        self.found_line_eq('+module:test::mod1::mod12::mod3', "pub mod <b>mod3</b> {}", 13)
        self.found_line_eq('+module:test::mod2::mod3', "pub mod <b>mod3</b> {}", 21)

    def test_mod_ref(self):
        # This method tests different kinds of module references. Each name
        # defines a different kind of module declaration (top-level vs nested,
        # single def vs multiple defs). We also test different kinds of references:
        # relative vs absolute paths, references in paths vs references in imports
        # (use items, specifically single imports, list imports, and glob imports),
        # reference via alias (pub use and use, with implicit and explicit alias).
        self.found_lines_eq('module-ref:mod1',
                            [('pub use <b>mod1</b>::mod12::bar;', 18),
                             ('::<b>mod1</b>::mod11::mod111::bar();', 25),
                             ('use <b>mod1</b>::mod11::mod111;', 30),
                             ('use <b>mod1</b>::mod11::mod111 as moda;', 31),
                             ('use <b>mod1</b>::mod12::*;', 38),
                             ('use <b>mod1</b>::{mod11, mod12};', 44),
                             ('use <b>mod1</b>::mod12::bar;', 51),
                             ('use <b>mod1</b>::mod12::bar as baz;', 57),
                             ('use <b>mod1</b>::mod12::{self, bar};', 63)])
        self.found_lines_eq('module-ref:mod2',
                            [('<b>mod2</b>::foo();', 26),
                             ('<b>mod2</b>::bar();', 27)])
        self.found_lines_eq('module-ref:mod11',
                            [('::mod1::<b>mod11</b>::mod111::bar();', 25),
                             ('use mod1::<b>mod11</b>::mod111;', 30),
                             ('use mod1::<b>mod11</b>::mod111 as moda;', 31),
                             ('<b>mod11</b>::mod111::bar();', 46)])
        self.found_lines_eq('module-ref:mod12',
                             [('pub use mod1::<b>mod12</b>::bar;', 18),
                              ('use mod1::<b>mod12</b>::*;', 38),
                              ('<b>mod12</b>::bar();', 47),
                              ('use mod1::<b>mod12</b>::bar;', 51),
                              ('use mod1::<b>mod12</b>::bar as baz;', 57),
                              ('use mod1::<b>mod12</b>::{self, bar};', 63),
                              ('<b>mod12</b>::bar();', 66)])
        self.found_lines_eq('module-ref:mod111',
                            [('::mod1::mod11::<b>mod111</b>::bar();', 25),
                             ('<b>mod111</b>::bar();', 33),
                             ('<b>moda</b>::bar();', 34),
                             ('mod11::<b>mod111</b>::bar();', 46)])
        self.found_line_eq('module-ref:moda', '<b>moda</b>::bar();', 34)

    def test_mod_ref_qual(self):
        # TODO I believe all the commented out lines are bugs
        self.found_lines_eq('+module-ref:test::mod1',
                            [('pub use <b>mod1</b>::mod12::bar;', 18),
                             #('::<b>mod1</b>::mod11::mod111::bar();', 25),
                             ('use <b>mod1</b>::mod11::mod111;', 30),
                             ('use <b>mod1</b>::mod11::mod111 as moda;', 31),
                             ('use <b>mod1</b>::mod12::*;', 38),
                             ('use <b>mod1</b>::{mod11, mod12};', 44),
                             ('use <b>mod1</b>::mod12::bar;', 51),
                             ('use <b>mod1</b>::mod12::bar as baz;', 57),
                             ('use <b>mod1</b>::mod12::{self, bar};', 63)])
        #self.found_lines_eq('+module-ref:test::mod2',
        #                    [('<b>mod2</b>::foo();', 26),
        #                     ('<b>mod2</b>::bar();', 27)])
        self.found_lines_eq('+module-ref:test::mod1::mod11',
                            [('::mod1::<b>mod11</b>::mod111::bar();', 25)])
                             #('use mod1::<b>mod11</b>::mod111;', 30),
                             #('use mod1::<b>mod11</b>::mod111 as moda;', 31),
                             #('<b>mod11</b>::mod111::bar();', 46)])
        # self.found_lines_eq('+module-ref:test::mod1::mod12',
        #                      [('pub use mod1::<b>mod12</b>::bar;', 18),
        #                       ('use mod1::<b>mod12</b>::*;', 38),
        #                       ('<b>mod12</b>::bar();', 47),
        #                       ('use mod1::<b>mod12</b>::bar;', 51),
        #                       ('use mod1::<b>mod12</b>::bar as baz;', 57),
        #                       ('use mod1::<b>mod12</b>::{self, bar};', 63),
        #                       ('<b>mod12</b>::bar();', 66)])
        self.found_lines_eq('+module-ref:test::mod1::mod11::mod111',
                            [('::mod1::mod11::<b>mod111</b>::bar();', 25),
                             ('<b>mod111</b>::bar();', 33),
                             ('<b>moda</b>::bar();', 34)])
                             #('mod11::<b>mod111</b>::bar();', 46)])
        self.found_line_eq('+module-ref:29$moda', '<b>moda</b>::bar();', 34)

    def test_mod_alias_ref(self):
        # FIXME(#24) There is no module-alias filter, and when there is, the result
        # at line 31 should be one, not a module-alias-ref
        self.found_lines_eq('module-alias-ref:moda',
                            [('use mod1::mod11::mod111 as <b>moda</b>;', 31),
                             ('<b>moda</b>::bar();', 34)])

    def test_mod_alias_ref_qual(self):
        # FIXME(#24) There is no module-alias filter, and when there is, the result
        # at line 31 should be one, not a module-alias-ref
        self.found_lines_eq('+module-alias-ref:29$moda',
                            [('use mod1::mod11::mod111 as <b>moda</b>;', 31),
                             ('<b>moda</b>::bar();', 34)])

    def test_mod_use(self):
        # TODO can't seem to test for empty lists
        #self.found_lines_eq('module-use:mod1', [])
        #self.found_lines_eq('module-use:mod2', [])
        # TODO use on 44
        #self.found_lines_eq('module-use:mod11', [])
        # TODO use on 44, 63
        #self.found_lines_eq('module-use:mod12', [])
        self.found_lines_eq('module-use:mod111',
                            [('use mod1::mod11::<b>mod111</b>;', 30),
                             ('use mod1::mod11::mod111 as <b>moda</b>;', 31)])

    def test_mod_use_qual(self):
        # TODO - TODOs from test_mod_use apply here too

        self.found_lines_eq('+module-use:test::mod1::mod11::mod111',
                            [('use mod1::mod11::<b>mod111</b>;', 30),
                             ('use mod1::mod11::mod111 as <b>moda</b>;', 31)])

