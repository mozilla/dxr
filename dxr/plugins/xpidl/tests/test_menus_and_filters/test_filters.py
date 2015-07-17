from dxr.testing import DxrInstanceTestCase


class IdlFilterQueryTest(DxrInstanceTestCase):
    """Test query filters for Idl structure."""

    def test_derived(self):
        self.found_line_eq('derived:nsISupports',
                           'interface nsIDownloadHistory : <b>nsISupports</b> {', 15)

    def test_type_decl(self):
        self.found_line_eq('type-decl:nsISupports', 'interface <b>nsISupports</b> {', 26)
        self.found_line_eq('type-decl:nsIDownloadHistory',
                           'interface <b>nsIDownloadHistory</b> : nsISupports {', 15)

    def test_function_decl(self):
        self.found_line_eq('function-decl:QueryInterface',
                           'void <b>QueryInterface</b>(in nsIIDRef uuid,', 27)
        self.found_line_eq('function-decl:addDownload',
                           'void <b>addDownload</b>(in nsIURI aSource, [optional] in nsIURI aReferrer,',
                           19)

    def test_var_decl(self):
        # Test for both 'const' and 'attribute' vars.
        self.found_line_eq('var-decl:EVENT_REORDER',
                           'const unsigned long <b>EVENT_REORDER</b> = 0x0003;', 33)
        self.found_line_eq('var-decl:description',
                           'readonly attribute AString <b>description</b>;', 37)
