from dxr.testing import DxrInstanceTestCase

class TraitTests(DxrInstanceTestCase):
    def test_trait_def(self):
        self.found_line_eq('type:Foo', "trait <b>Foo</b> {", 3)

    def test_trait_ref(self):
        self.found_lines_eq('type-ref:Foo',
                            [("trait Bar: <b>Foo</b> {}", 6),
                             ("impl <b>Foo</b> for i32 {}", 8),
                             ("fn foo&lt;X: <b>Foo</b>&gt;(x: &amp;X) {}", 11),
                             ("impl <b>Foo</b> for Baz {}", 15),
                             ("let _y: &amp;<b>Foo</b> = &amp;x;", 19)])

    def test_trait_super(self):
        self.found_line_eq('bases:Bar', "trait <b>Foo</b> {", 3)

    def test_trait_sub(self):
        self.found_line_eq('derived:Foo', "trait <b>Bar</b>: Foo {}", 6)

    def test_trait_impls(self):
        self.found_lines_eq('impl:Foo',
                            [("impl Foo for <b>i32</b> {}", 8),
                             ("impl Foo for <b>Baz</b> {}", 15)])
        self.found_line_eq('impl:Baz', "impl Foo for <b>Baz</b> {}", 15)

    def test_trait_def_qual(self):
        self.found_line_eq('+type:test::Foo', "trait <b>Foo</b> {", 3)

    def test_trait_ref_qual(self):
        self.found_lines_eq('+type-ref:test::Foo',
                            [("trait Bar: <b>Foo</b> {}", 6),
                             ("impl <b>Foo</b> for i32 {}", 8),
                             ("fn foo&lt;X: <b>Foo</b>&gt;(x: &amp;X) {}", 11),
                             ("impl <b>Foo</b> for Baz {}", 15),
                             ("let _y: &amp;<b>Foo</b> = &amp;x;", 19)])

    def test_trait_super_qual(self):
        self.found_line_eq('+bases:test::Bar', "trait <b>Foo</b> {", 3)

    def test_trait_sub_qual(self):
        self.found_line_eq('+derived:test::Foo', "trait <b>Bar</b>: Foo {}", 6)

    def test_trait_impls_qual(self):
        self.found_lines_eq('+impl:test::Foo',
                            [("impl Foo for <b>i32</b> {}", 8),
                             ("impl Foo for <b>Baz</b> {}", 15)])
        self.found_line_eq('+impl:test::Baz', "impl Foo for <b>Baz</b> {}", 15)
