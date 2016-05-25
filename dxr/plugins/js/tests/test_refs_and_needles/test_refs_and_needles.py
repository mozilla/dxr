"""Test that the plugin produces correct needles and refs.

"""
from dxr.testing import DxrInstanceTestCase, menu_on


class RefNeedlesTests(DxrInstanceTestCase):
    def test_needles(self):
        self.found_line_eq("id:foo",
                           "let <b>foo</b> = {", 3)
        self.found_line_eq("id:y",
                           "function identity(<b>y</b>) {", 8)
        self.found_line_eq("id:identity",
                           "function <b>identity</b>(y) {", 8)
        self.found_line_eq("ref:y",
                           "return <b>y</b>;", 9)
        self.found_line_eq("ref:foo",
                           "stuff.doStuff(<b>foo</b>);", 16)
        self.found_line_eq("+id:Guy#fun",
                           "this.<b>fun</b> = function thathasaname() {", 21)
        self.found_line_eq("+ref:somejs.js-8",
                           'return "HI " + <b>other</b>;', 27)

    def test_menus(self):
        page = self.source_page('somejs.js')

        menu_on(page, 'echo', {'html': 'Find definition of prop echo',
                               'href': '/code/search?q=%2Bid%3A%22foo%23echo%22'})
        menu_on(page, 'echo', {'html': 'Find references to prop echo',
                               'href': '/code/search?q=%2Bref%3A%22foo%23echo%22'})

        menu_on(page, 'print', {'html': 'Find definition of prop print',
                                'href': '/code/search?q=%2Bid%3A%22foo%23print%22'})
        menu_on(page, 'print', {'html': 'Find references to prop print',
                                'href': '/code/search?q=%2Bref%3A%22foo%23print%22'})

        menu_on(page, 'identity2', {'html': 'Find definition of var identity2',
                                    'href': '/code/search?q=%2Bid%3A%22somejs.js-3%22'})
        menu_on(page, 'identity2', {'html': 'Find references to var identity2',
                                    'href': '/code/search?q=%2Bref%3A%22somejs.js-3%22'})

        menu_on(page, 'Guy', {'html': 'Find definition of prop Guy',
                              'href': '/code/search?q=%2Bid%3A%22%23Guy%22'})
        menu_on(page, 'Guy', {'html': 'Find references to prop Guy',
                              'href': '/code/search?q=%2Bref%3A%22%23Guy%22'})

        menu_on(page, 'thathasaname', {'html': 'Find definition of var thathasaname',
                                       'href': '/code/search?q=%2Bid%3A%22somejs.js-7%22'})
        menu_on(page, 'thathasaname', {'html': 'Find references to var thathasaname',
                                       'href': '/code/search?q=%2Bref%3A%22somejs.js-7%22'})

        menu_on(page, 'fun', {'html': 'Find definition of prop fun',
                                       'href': '/code/search?q=%2Bid%3A%22Guy%23fun%22'})
        menu_on(page, 'fun', {'html': 'Find references to prop fun',
                                       'href': '/code/search?q=%2Bref%3A%22Guy%23fun%22'})
