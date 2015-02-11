from textwrap import dedent

from dxr.plugins.python.tests import PythonSingleFileTestCase


class DerivedTests(PythonSingleFileTestCase):
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

    def test_builtin_class(self):
        self.found_lines_eq('derived:object', [
            'class <b>Grandparent</b>(object):',
            'class <b>Parent</b>(Grandparent):',
            'class <b>Parent2</b>(Grandparent):',
            'class <b>Child</b>(Parent, Parent2):',
        ])

    def test_grandparent(self):
        self.found_lines_eq('derived:Grandparent', [
            'class <b>Parent</b>(Grandparent):',
            'class <b>Parent2</b>(Grandparent):',
            'class <b>Child</b>(Parent, Parent2):',
        ])

    def test_parent(self):
        self.found_line_eq('derived:Parent', 'class <b>Child</b>(Parent, Parent2):')
        self.found_line_eq('derived:Parent2', 'class <b>Child</b>(Parent, Parent2):')

    def test_child(self):
        self.found_nothing('derived:Child')

    def test_absolute_name(self):
        """Make sure you can match on the absolute name of a class."""
        self.found_lines_eq('derived:main.Grandparent', [
            'class <b>Parent</b>(Grandparent):',
            'class <b>Parent2</b>(Grandparent):',
            'class <b>Child</b>(Parent, Parent2):',
        ])
