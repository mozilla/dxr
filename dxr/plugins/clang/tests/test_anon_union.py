from dxr.plugins.clang.tests import CSingleFileTestCase
from dxr.testing import menu_on


class AnonymousUnionTests(CSingleFileTestCase):
    source = """
        struct S
        {
            int foo;
            union
            {
                float bar;
                double baz;
            };
        };

        int main()
        {
            S s;
            s.foo = 1;
            s.bar = 2.0f;
            s.baz = 3.0;
            return 0;
        }
        """

    def test_search_refs(self):
        """Menu can search for references to members of anonymous unions."""
        menu_on(self.source_page(self.source_filename),
                'bar',
                {'html': 'Find references',
                 'href': '/code/search?q=%2Bvar-ref%3A%22S%3A%3A%28anonymous+union%29%3A%3Abar%22'})

        menu_on(self.source_page(self.source_filename),
                'baz',
                {'html': 'Find references',
                 'href': '/code/search?q=%2Bvar-ref%3A%22S%3A%3A%28anonymous+union%29%3A%3Abaz%22'})

    def test_search_defs(self):
        """Menu can search for definitions of members of anonymous unions."""
        menu_on(self.source_page(self.source_filename),
                'bar',
                {'html': 'Jump to definition',
                 'href': '/code/source/%s#7' % self.source_filename},
                text_instance=2)

        menu_on(self.source_page(self.source_filename),
                'baz',
                {'html': 'Jump to definition',
                 'href': '/code/source/%s#8' % self.source_filename},
                text_instance=2)
