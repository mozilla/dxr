from dxr.plugins.rust.tests import RustDxrInstanceTestCase

class FunctionTests(RustDxrInstanceTestCase):
    def test_simple_function(self):
        self.found_line_eq('function:foo', "fn <b>foo</b>() {", 3)

    def test_methods_are_functions_too(self):
        # Test a method in an inherant impl.
        self.found_line_eq('function:baz', "fn <b>baz</b>(&amp;self) {}", 10)
        # Test the declaration and definition of a required trait method.
        self.found_lines_eq('function:qux',
                            [('fn <b>qux</b>(&amp;self);', 16),
                             ('fn <b>qux</b>(&amp;self) {}', 23)])
        # Test a provided trait method.
        self.found_line_eq('function:norf', 'fn <b>norf</b>(&amp;self) {', 17)

    def test_multiple_with_same_name(self):
        self.found_lines_eq('function:bar',
                            [("fn <b>bar</b>() {}", 12),
                             ("fn <b>bar</b>() {}", 26)])

    def test_fn_ref(self):
        self.found_line_eq('function-ref:foo', "<b>foo</b>();", 39)

    def test_method_ref(self):
        self.found_line_eq('function-ref:baz', "b.<b>baz</b>();", 42)
        self.found_lines_eq('function-ref:qux',
                            [('self.<b>qux</b>();', 18),
                             ('x.<b>qux</b>();', 29),
                             ('x.<b>qux</b>();', 34),
                             ('b.<b>qux</b>();', 44),
                             ('Foo::<b>qux</b>(&amp;b);', 45),
                             ('&lt;Baz as Foo&gt;::<b>qux</b>(&amp;b);', 46)])
        self.found_lines_eq('function-ref:norf',
                            [('x.<b>norf</b>();', 30),
                             ('x.<b>norf</b>();', 35),
                             ('b.<b>norf</b>();', 48),
                             ('Foo::<b>norf</b>(&amp;b);', 49),
                             ('&lt;Baz as Foo&gt;::<b>norf</b>(&amp;b);', 50)])

    def test_simple_function_qual(self):
        self.found_line_eq('+function:test::foo', "fn <b>foo</b>() {", 3)

    # FIXME this fails, but test::foo works, so I think qualname searches with case insensitive is broken
    #def test_case_insensitive_qual(self):
    #    self.found_line_eq('+function:TEST::FOO', "fn <b>foo</b>() {", 3)

    # FIXME should be test::<Baz>::baz
    def test_methods_are_functions_too_qual(self):
        self.found_line_eq('+function:<Baz>::baz', "fn <b>baz</b>(&amp;self) {}", 10)
        self.found_line_eq('function:test::Foo::qux', 'fn <b>qux</b>(&amp;self);', 16)
        # TODO
        #self.found_line_eq('function:test::<Baz as Foo>::qux', 'fn <b>qux</b>(&self) {}', 23)
        self.found_line_eq('function:test::Foo::norf', 'fn <b>norf</b>(&amp;self) {', 17)

    # FIXME should be test::<Baz>::baz
    def test_multiple_with_same_name_qual(self):
        # Note that only one bar matches the qualname
        self.found_line_eq('+function:<Baz>::bar', "fn <b>bar</b>() {}", 12)

    def test_fn_ref_qual(self):
        self.found_line_eq('+function-ref:test::foo', "<b>foo</b>();", 39)

    # FIXME should be test::<Baz>::baz
    def test_method_ref_qual(self):
        self.found_line_eq('+function-ref:<Baz>::baz', "b.<b>baz</b>();", 42)
        self.found_lines_eq('+function-ref:test::Foo::qux',
                            [('self.<b>qux</b>();', 18),
                             ('x.<b>qux</b>();', 29),
                             ('x.<b>qux</b>();', 34),
                             ('b.<b>qux</b>();', 44),
                             ('Foo::<b>qux</b>(&amp;b);', 45),
                             ('&lt;Baz as Foo&gt;::<b>qux</b>(&amp;b);', 46)])
        self.found_lines_eq('+function-ref:test::Foo::norf',
                            [('x.<b>norf</b>();', 30),
                             ('x.<b>norf</b>();', 35),
                             ('b.<b>norf</b>();', 48),
                             ('Foo::<b>norf</b>(&amp;b);', 49),
                             ('&lt;Baz as Foo&gt;::<b>norf</b>(&amp;b);', 50)])

