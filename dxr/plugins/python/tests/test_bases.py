from textwrap import dedent

from dxr.plugins.python.tests import PythonSingleFileTestCase


class BasesTests(PythonSingleFileTestCase):
    source = dedent("""
    class Grandparent(object):
        pass

    class Parent(Grandparent):
        pass

    class Parent2(Grandparent):
        pass

    class Child(Parent, Parent2):
        pass
    """)
    def test_child(self):
        self.found_lines_eq('bases:Child', [
            'class <b>Grandparent</b>(object):',
            'class <b>Parent</b>(Grandparent):',
            'class <b>Parent2</b>(Grandparent):',
        ])

    def test_parent(self):
        self.found_line_eq('bases:Parent', 'class <b>Grandparent</b>(object):')
        self.found_line_eq('bases:Parent2', 'class <b>Grandparent</b>(object):')

    def test_grandparent(self):
        self.found_nothing('bases:Grandparent')

    def test_absolute_name(self):
        """Make sure you can match on the absolute name of a class."""
        self.found_line_eq('bases:main.Parent', 'class <b>Grandparent</b>(object):')
