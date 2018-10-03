"""Tests for queries about superclasses and subclasses"""

from dxr.plugins.clang.tests import CSingleFileTestCase


class InheritanceTests(CSingleFileTestCase):
    source = r"""
        class A {
        };

        class B1 : public A {
        };
        class B2 : public A {
        };

        class C : public B1, public B2 {
        };

        struct D {
        };

        struct E : public D {
        };
        """

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

    # I'm assuming that if bases/derived queries on structs are working at all
    # then they're working the same way as for classes, so I'm not repeating all
    # of the class tests here.
    def test_substructs(self):
        """Make sure we find substructs."""
        self.found_line_eq(
            'derived:D',
            'struct <b>E</b> : public D {')

    def test_base_structs(self):
        """Make sure we find base structs."""
        self.found_line_eq(
            'bases:E',
            'struct <b>D</b> {')
