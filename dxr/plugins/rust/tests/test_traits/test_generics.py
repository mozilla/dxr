from dxr.plugins.rust.tests import RustDxrInstanceTestCase

class GenericsTests(RustDxrInstanceTestCase):
    def test_generic_def(self):
        # FIXME(#23) perhaps better not to need the scope id for type variables
        self.found_line_eq('type:X$23', "fn foo&lt;<b>X</b>: Foo&gt;(x: &amp;X) {}", 11)

    def test_generic_ref(self):
        # FIXME(#23) perhaps better not to need the scope id for type variables
        self.found_line_eq('type-ref:X$23', "fn foo&lt;X: Foo&gt;(x: &amp;<b>X</b>) {}", 11)

    def test_generic_def_qual(self):
        # FIXME(#23) perhaps better not to need the scope id for type variables
        self.found_line_eq('+type:test::foo::X$23', "fn foo&lt;<b>X</b>: Foo&gt;(x: &amp;X) {}", 11)

    def test_generic_ref_qual(self):
        # FIXME(#23) perhaps better not to need the scope id for type variables
        self.found_line_eq('+type-ref:test::foo::X$23', "fn foo&lt;X: Foo&gt;(x: &amp;<b>X</b>) {}", 11)

    def test_generic_def_case_insensitive(self):
        # FIXME(#23) perhaps better not to need the scope id for type variables
        self.found_line_eq('type:x$23', "fn foo&lt;<b>X</b>: Foo&gt;(x: &amp;X) {}", 11)

    def test_generic_ref_case_insensitive(self):
        # FIXME(#23) perhaps better not to need the scope id for type variables
        self.found_line_eq('type-ref:x$23', "fn foo&lt;X: Foo&gt;(x: &amp;<b>X</b>) {}", 11)

    def test_generic_def_qual_case_insensitive(self):
        # FIXME(#23) perhaps better not to need the scope id for type variables
        # self.found_line_eq('+type:TEST::Foo::X$25', "fn foo&lt;<b>X</b>: Foo&gt;(x: &amp;X) {}", 11)
        # TODO qualname/case sensitivity bug
        pass

    def test_generic_ref_qual_case_insensitive(self):
        # FIXME(#23) perhaps better not to need the scope id for type variables
        # self.found_line_eq('+type-ref:test::foo::x$25', "fn foo&lt;X: Foo&gt;(x: &amp;<b>X</b>) {}", 11)
        # TODO qualname/case sensitivity bug
        pass
