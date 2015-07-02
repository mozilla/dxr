from dxr.testing import DxrInstanceTestCase, menu_on

SEARCH = '/code/search?q=%s%%3A%s'


class IdlMenusTest(DxrInstanceTestCase):
    """Test that menu links point to the right places."""

    def test_include(self):
        menu_on(self.source_page("nsIDownloadHistory.idl"), 'nsISupports.idl',
                {'html': 'Jump to file', 'href': '/code/source/nsISupports.idl'})

    def test_forward_decl(self):
        page = self.source_page("nsIDownloadHistory.idl")
        menu_on(page, 'nsIURI', {'html': 'See generated source',
                                 'href': '/code/source/obj/nsIDownloadHistory.h#17'})
        menu_on(page, 'nsIURI',
                {'html': 'Find declaration', 'href': SEARCH % ('type-decl', 'nsIURI')})
        menu_on(page, 'nsIURI',
                {'html': 'Find subclasses', 'href': SEARCH % ('derived', 'nsIURI')})

    def test_interface(self):
        page = self.source_page("nsIDownloadHistory.idl")
        menu_on(page, 'nsIDownloadHistory',
                {'html': 'See generated source',
                 'href': '/code/source/obj/nsIDownloadHistory.h#20'})
        menu_on(page, 'nsIDownloadHistory',
                {'html': 'Find subclasses', 'href': SEARCH % ('derived', 'nsIDownloadHistory')})

    def test_method(self):
        page = self.source_page("nsIDownloadHistory.idl")
        menu_on(page, 'addDownload',
                {'html': 'Find declaration', 'href': SEARCH % ('function-decl', 'addDownload')})
        menu_on(page, 'addDownload',
                {'html': 'Find implementations', 'href': SEARCH % ('function', 'addDownload')})

    def test_type_decl(self):
        menu_on(self.source_page("nsrootidl.idl"), 'PRTime',
                {'html': 'See generated source', 'href': '/code/source/obj/nsrootidl.h#36'})
