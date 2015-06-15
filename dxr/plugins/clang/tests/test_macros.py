from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class MacroTests(SingleFileTestCase):
    """Tests for ``macro`` queries"""

    source = """
        #define MACRO
        #define ADD(x, y) ((x) + (y))

        """ + MINIMAL_MAIN

    def test_simple(self):
        """Make sure macro definitions are found."""
        self.found_line_eq('macro:MACRO', '#define <b>MACRO</b>')

    def test_parametrized(self):
        """Make sure parametrized macro definitions are found."""
        self.found_line_eq('macro:ADD', '#define <b>ADD</b>(x, y) ((x) + (y))')


class MacroRefTests(SingleFileTestCase):
    """Tests for ``+macro-ref`` queries"""

    source = """
        #define MACRO

        #ifdef MACRO
        #endif

        #ifndef MACRO
        #endif
        
        #if defined(MACRO)
        #endif

        #undef MACRO
        """ + MINIMAL_MAIN

    def test_refs(self):
        self.found_lines_eq('+macro-ref:MACRO', [
            # Test that a macro mentioned in an #ifdef directive is treated as
            # a reference:
            ('#ifdef <b>MACRO</b>', 4),

            # Test that a macro mentioned in an #ifndef directive is treated as
            # a reference:
            ('#ifndef <b>MACRO</b>', 7),

            # Test that a macro mentioned in an #if defined() expression is
            # treated as a reference:
            ('#if defined(<b>MACRO</b>)', 10),

            # Test that a macro mentioned in an #undef directive is treated as
            # a reference:
            ('#undef <b>MACRO</b>', 13)])


class MacroArgumentReferenceTests(SingleFileTestCase):
    source = """
        #define ID2(x) (x)
        #define ID(x) ID2(x)
        #define ADD(x, y) ((x) + (y))
        int foo()
        {
            int x = 0;
            int y = 0;
            return
                ID(x) +
                ID(y) +
                ADD(x, y);
        }
        """ + MINIMAL_MAIN

    def test_refs(self):
        """Test variables referenced in macro arguments"""
        self.found_lines_eq('+var-ref:foo()::x', [
            ('ID(<b>x</b>) +', 10),
            ('ADD(<b>x</b>, y);', 12)])
        self.found_lines_eq('+var-ref:foo()::y', [
            ('ID(<b>y</b>) +', 11),
            ('ADD(x, <b>y</b>);', 12)])


class MacroArgumentFieldReferenceTests(SingleFileTestCase):
    source = """
        #define ID2(x) (x)
        #define ID(x) ID2(x)
        #define FOO(x) foo.x
        #define FIELD(s, x) s.x

        struct Foo
        {
            int bar;
        };

        int baz()
        {
            Foo foo = { 0 };
            return
                ID(foo.bar) +
                FOO(bar) +
                FIELD(foo, bar);
        }
        """ + MINIMAL_MAIN

    def test_refs(self):
        """Test struct fields referenced in macro arguments"""
        self.found_lines_eq('+var-ref:baz()::foo', [
            ('ID(<b>foo</b>.bar) +', 16),
            ('FIELD(<b>foo</b>, bar);', 18)])
        self.found_lines_eq('+var-ref:Foo::bar', [
            ('ID(foo.<b>bar</b>) +', 16),
            ('FOO(<b>bar</b>) +', 17),
            ('FIELD(foo, <b>bar</b>);', 18)])


class MacroArgumentDeclareTests(SingleFileTestCase):

    source = """
        #define ID2(x) x
        #define ID(x) ID2(x)
        #define DECLARE(x) int x = 0
        #define DECLARE2(x, y) int x = 0, y = 0
        void foo()
        {
            ID(int a = 0);
            DECLARE(b);
            DECLARE2(c, d);
        }
        """ + MINIMAL_MAIN

    def test_decls(self):
        """Test variables declared in macro arguments"""
        self.found_line_eq('+var:foo()::a', 'ID(int <b>a</b> = 0);')
        self.found_line_eq('+var:foo()::b', 'DECLARE(<b>b</b>);')
        self.found_line_eq('+var:foo()::c', 'DECLARE2(<b>c</b>, d);')
        self.found_line_eq('+var:foo()::d', 'DECLARE2(c, <b>d</b>);')
