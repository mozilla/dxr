from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


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
