from textwrap import dedent
from nose.tools import raises

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


class NameCycleTests(PythonSingleFileTestCase):
    """In class inheritance processing, we currently don't distinguish between
    a local name and a built-in name, so even though python doesn't permit
    inheritance cycles, it can appear to us that we do have cycles - make sure
    we cut them off.

    """
    # DeprecationWarning and UserWarning belong to the exceptions module, but
    # python exposes them in the built-in namespace, so they don't need to be
    # explicitly imported.
    source = dedent("""
    class DeprecationWarning(DeprecationWarning):
        pass

    class Oops(UserWarning):
        pass
    class UserWarning(Oops):
        pass
    """)

    def test_inheritance_name_cycles(self):
        """Make sure we don't crash on indexing, and test that we return
        reasonable results for the part of the inheritance graph we don't cut
        off.

        """
        self.found_nothing('bases:main.DeprecationWarning')
        self.found_lines_eq('derived:main.Oops', [
            'class <b>UserWarning</b>(Oops):'
            ])
        self.found_lines_eq('bases:main.UserWarning', [
            'class <b>Oops</b>(UserWarning):'
            ])

    @raises(AssertionError)  # remove this line when fixed
    def test_inheritance_name_cycle_lookup_looping(self):
        """Make sure we don't find the wrong name (local vs. built-in) on
        base: and derived: searches when we have an inheritance name cycle.

        """
        self.found_nothing('bases:main.Oops')
        self.found_nothing('derived:main.UserWarning')
