from textwrap import dedent
from urllib import quote

from dxr.plugins.python.tests import PythonSingleFileTestCase
from dxr.testing import DxrInstanceTestCase, menu_on


def search(query):
    return '/code/search?q=' + quote(query)


def browse(path, lineno=None):
    return '/code/source/' + path + (('#' + unicode(lineno)) if lineno else '')


class ClassMenuTests(PythonSingleFileTestCase):
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


class MenuTests(DxrInstanceTestCase):
    def test_definition_menu_module(self):
        """Make sure the definition menu works for module-level
        calls.

        """
        menu_on(self.source_page('main.py'), 'foo',
            {'html': 'Jump to definition',
             'href': browse('functions.py', 1)},
        )
