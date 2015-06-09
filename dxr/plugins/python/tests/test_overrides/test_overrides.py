from textwrap import dedent

from dxr.plugins.python.tests import PythonSingleFileTestCase
from dxr.testing import DxrInstanceTestCase


class OverridesTests(PythonSingleFileTestCase):
    source = dedent("""
    class Grandparent(object):
        def overridden_all(self): #grandparent
            '''Overridden in all children.'''

        def not_overridden(self): #grandparent
            '''Not overridden in any children.'''

    class Parent(Grandparent):
        def overridden_all(self): #parent
            '''Overridden in all children.'''

        def overridden_child(self): #parent
            '''Overridden in the child class.'''


    class Child(Parent):
        def overridden_all(self): #child
            '''Overridden in all children.'''

        def overridden_child(self): #child
            '''Overridden in the child class.'''
    """)

    def test_overrides_direct(self):
        """Make sure that overrides: finds methods overridden in child
        classes.

        """
        self.found_line_eq('overrides:overridden_child',
                           'def <b>overridden_child</b>(self): #child')

    def test_overrides_multiple(self):
        """Make sure that overrides: finds methods overridden in
        multiple descendants.

        """
        self.found_lines_eq('overrides:overridden_all', [
            'def <b>overridden_all</b>(self): #parent',
            'def <b>overridden_all</b>(self): #child'
        ])

    def test_overrides_nothing(self):
        """Make sure that overrides: finds nothing for methods that are
        not overridden.

        """
        self.found_nothing('overrides:not_overridden')

    def test_overrides_qualname(self):
        """Make sure that overrides: supports qualnames."""
        self.found_line_eq('overrides:main.Parent.overridden_child',
                           'def <b>overridden_child</b>(self): #child')

    def test_overridden_direct(self):
        """Make sure that overridden: finds methods overridden from
        parent classes.

        """
        self.found_line_eq('overridden:overridden_child',
                           'def <b>overridden_child</b>(self): #parent')

    def test_overridden_multiple(self):
        """Make sure that overridden: finds methods overridden from
        multiple parents.

        """
        self.found_lines_eq('overridden:overridden_all', [
            'def <b>overridden_all</b>(self): #grandparent',
            'def <b>overridden_all</b>(self): #parent'
        ])

    def test_overridden_nothing(self):
        """Make sure that overridden: finds nothing for methods that are
        not overridden.

        """
        self.found_nothing('overridden:not_overridden')

    def test_overridden_qualname(self):
        """Make sure that overridden: supports qualnames."""
        self.found_line_eq('overridden:main.Child.overridden_child',
                           'def <b>overridden_child</b>(self): #parent')


class ImportOverrideTests(DxrInstanceTestCase):
    def test_overrides(self):
        """Make sure the overrides filter works across imports."""
        self.found_line_eq('overrides:parent.Parent.overridden',
                           'def <b>overridden</b>(self):', 5)

    def test_overridden(self):
        """Make sure the overridden filter works across imports."""
        self.found_line_eq('overridden:child.Child.overridden',
                           'def <b>overridden</b>(self):', 2)
