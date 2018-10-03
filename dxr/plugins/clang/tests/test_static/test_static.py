from dxr.testing import DxrInstanceTestCase


class AnonymousNamespaceTests(DxrInstanceTestCase):
    """Tests for static file-scoped functions"""

    def test_function(self):
        self.found_line_eq('+function:"(static in main.cpp)::foo()"',
                           'static void <b>foo</b>() /* in main */', 4)
        self.found_line_eq('+function:"(static in main2.cpp)::foo()"',
                           'static void <b>foo</b>() /* in main2 */', 4)

    def test_function_ref(self):
        self.found_line_eq('+function-ref:"(static in main.cpp)::foo()"',
                           '<b>foo</b>();  /* calling foo in main */', 10)
        self.found_line_eq('+function-ref:"(static in main2.cpp)::foo()"',
                           '<b>foo</b>();  /* calling foo in main2 */', 10)

    def test_anonymous_namespace_in_header(self):
        self.found_line_eq('+function:"(static in main3.h)::baz()"',
                           'static void <b>baz</b>() /* in main3.h */', 1)
        self.found_files_eq('+function-ref:"(static in main3.h)::baz()"', [
            "main.cpp",
            "main2.cpp"])

