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
            (4, '#ifdef <b>MACRO</b>'),

            # Test that a macro mentioned in an #ifndef directive is treated as
            # a reference:
            (7, '#ifndef <b>MACRO</b>'),

            # Test that a macro mentioned in an #if defined() expression is
            # treated as a reference:
            (10, '#if defined(<b>MACRO</b>)'),

            # Test that a macro mentioned in an #undef directive is treated as
            # a reference:
            (13, '#undef <b>MACRO</b>')])
