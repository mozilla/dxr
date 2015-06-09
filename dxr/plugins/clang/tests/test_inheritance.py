"""Tests for queries about superclasses and subclasses"""

from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class InheritanceTests(SingleFileTestCase):
    source = r"""
        class A {
        };

        class B1 : public A {
        };
        class B2 : public A {
        };

        class C : public B1, public B2 {
        };
        """ + MINIMAL_MAIN

    def test_subclasses(self):
        """We should find all direct and indirect subclasses."""
        self.found_lines_eq(
            'derived:A',
            ['class <b>B1</b> : public A {',
             'class <b>B2</b> : public A {',
             'class <b>C</b> : public B1, public B2 {'])

    def test_no_subclasses(self):
        """If there aren't any subclasses, don't find any."""
        self.found_nothing('derived:C')

    def test_superclasses(self):
        """We should find all direct and indirect superclasses, even in this
        icky diamond-shaped inheritance.

        """
        self.found_lines_eq(
            'bases:C',
            ['class <b>A</b> {',
             'class <b>B1</b> : public A {',
             'class <b>B2</b> : public A {'])

    def test_no_superclasses(self):
        """If there aren't any superclasses, don't find any."""
        self.found_nothing('bases:A')
