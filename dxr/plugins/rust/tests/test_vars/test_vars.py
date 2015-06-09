from dxr.testing import DxrInstanceTestCase

class VarTests(DxrInstanceTestCase):
    def test_var_def(self):
        self.found_line_eq('var:a', "let <b>a</b> = 32i32;", 31)
        self.found_line_eq('var:w', "<b>w</b> @ _ =&gt; {", 24)
        self.found_line_eq('var:z', "<b>z</b> =&gt; {", 18)

    def test_arg_def(self):
        self.found_lines_eq('var:x', [("fn foo(<b>x</b>: u8) -&gt; u8 {", 3),
                                      ("let <b>x</b> = 2u8;", 9),
                                      ("let <b>x</b> = 5 + x;", 12)])

    def test_var_ref(self):
        self.found_line_eq('var-ref:a', "let _ = <b>a</b> + 10;", 32)
        self.found_line_eq('var-ref:w', "let _ = <b>w</b>;", 25)
        self.found_line_eq('var-ref:z', "foo(<b>z</b> as u8);", 19)
        self.found_lines_eq('var-ref:x', [("return <b>x</b>;", 5),
                                          ("let x = 5 + <b>x</b>;", 12),
                                          ("<b>x</b>", 13)])

    def test_var_def_qual(self):
        self.found_line_eq('+var:a$65', "let <b>a</b> = 32i32;", 31)
        self.found_line_eq('+var:w$52', "<b>w</b> @ _ =&gt; {", 24)
        self.found_line_eq('+var:z$41', "<b>z</b> =&gt; {", 18)

    def test_arg_def_qual(self):
        self.found_line_eq('+var:test::foo::x', "fn foo(<b>x</b>: u8) -&gt; u8 {", 3)

    def test_var_ref_qual(self):
        self.found_line_eq('+var-ref:a$65', "let _ = <b>a</b> + 10;", 32)
        self.found_line_eq('+var-ref:w$52', "let _ = <b>w</b>;", 25)
        self.found_line_eq('+var-ref:z$41', "foo(<b>z</b> as u8);", 19)
        self.found_lines_eq('+var-ref:test::foo::x', [("return <b>x</b>;", 5),
                                                      ("let x = 5 + <b>x</b>;", 12)])
