from dxr.testing import DxrInstanceTestCase


class AnonymousNamespaceTests(DxrInstanceTestCase):
    """Tests for anonymous namespaces"""

    def test_function(self):
        self.found_line_eq('+function:"(anonymous namespace in main.cpp)::foo()"',
                           'void <b>foo</b>() /* in main */', 6)
        self.found_line_eq('+function:"(anonymous namespace in main2.cpp)::foo()"',
                           'void <b>foo</b>() /* in main2 */', 6)

    def test_function_ref(self):
        self.found_line_eq('+function-ref:"(anonymous namespace in main.cpp)::foo()"',
                           '<b>foo</b>();  /* calling foo in main */', 13)
        self.found_line_eq('+function-ref:"(anonymous namespace in main2.cpp)::foo()"',
                           '<b>foo</b>();  /* calling foo in main2 */', 13)

    def test_anonymous_namespace_in_header(self):
        self.found_line_eq('+function:"(anonymous namespace in main3.h)::baz()"',
                           'void <b>baz</b>() /* in main3.h */', 3)
        self.found_files_eq('+function-ref:"(anonymous namespace in main3.h)::baz()"', [
            "main.cpp",
            "main2.cpp"])

