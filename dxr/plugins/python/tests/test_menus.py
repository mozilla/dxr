from textwrap import dedent
from urllib import quote

from dxr.plugins.python.tests import PythonSingleFileTestCase
from dxr.testing import menu_on


def search(query):
    return '/code/search?q=' + quote(query)


class MenuTests(PythonSingleFileTestCase):
    source = dedent("""
    class Foo(object):
        def bar(self):
            return 'baz'
    """)

    def test_class_menu(self):
        menu_on(self.source_page('main.py'), 'Foo',
            {'html': 'Find subclasses',
             'href': search('+derived:main.Foo')},
            {'html': 'Find base classes',
             'href': search('+bases:main.Foo')}
        )
