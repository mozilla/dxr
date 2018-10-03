"""Tests for "Jump to definition" from a declaration

These ensure that decldefs without a defloc don't prevent the
"Jump to definition" menu item from appearing.

"""
from dxr.testing import DxrInstanceTestCase, menu_on


class DeclJumpToDefinitionTests(DxrInstanceTestCase):
    def test_type_ref1(self):
        menu_on(self.source_page('shared.h'),
                'type_in_main',
                {'html': 'Jump to definition',
                 'href': '/code/source/main.cpp#3'})

    def test_type_ref2(self):
        menu_on(self.source_page('shared.h'),
                'type_in_second',
                {'html': 'Jump to definition',
                 'href': '/code/source/second.cpp#3'})

    def test_var_ref1(self):
        menu_on(self.source_page('shared.h'),
                'var_in_main',
                {'html': 'Jump to definition',
                 'href': '/code/source/main.cpp#7'})

    def test_var_ref2(self):
        menu_on(self.source_page('shared.h'),
                'var_in_second',
                {'html': 'Jump to definition',
                 'href': '/code/source/second.cpp#7'})

    def test_function_ref1(self):
        menu_on(self.source_page('shared.h'),
                'function_in_main',
                {'html': 'Jump to definition',
                 'href': '/code/search?q=%2Bfunction%3Afunction_in_main%28%29&redirect=true'})

    def test_function_ref2(self):
        menu_on(self.source_page('shared.h'),
                'function_in_second',
                {'html': 'Jump to definition',
                 'href': '/code/search?q=%2Bfunction%3Afunction_in_second%28%29&redirect=true'})

