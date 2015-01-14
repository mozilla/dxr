from dxr.testing import DxrInstanceTestCase


class AnonymousNamespaceTests(DxrInstanceTestCase):
    """Tests for anonymous namespaces"""

    def test_function(self):
        self.found_line_eq('+function:"(anonymous namespace in main.cpp)::foo()"',
                           'void <b>foo</b>() /* in main */', 5)
        self.found_line_eq('+function:"(anonymous namespace in main2.cpp)::foo()"',
                           'void <b>foo</b>() /* in main2 */', 5)

    def test_function_ref(self):
        self.found_line_eq('+function-ref:"(anonymous namespace in main.cpp)::foo()"',
                           '<b>foo</b>();  /* calling foo in main */', 12)
        self.found_line_eq('+function-ref:"(anonymous namespace in main2.cpp)::foo()"',
                           '<b>foo</b>();  /* calling foo in main2 */', 12)
