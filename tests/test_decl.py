"""Tests for searches for declarations"""

from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class TypeDeclarationTests(SingleFileTestCase):
    """Tests for declarations of types"""

    source = r"""
        class MyClass;
        class MyClass
        {
        };
        """ + MINIMAL_MAIN

    def test_type(self):
        """Try searching for type declarations."""
        self.found_line_eq(
            'type-decl:MyClass', 'class <b>MyClass</b>;')


class FunctionDeclarationTests(SingleFileTestCase):
    """Tests for declarations of functions"""

    source = r"""
        void foo();
        void foo()
        {
        };
        """ + MINIMAL_MAIN

    def test_function(self):
        """Try searching for function declarations."""
        self.found_line_eq(
            'function-decl:foo', 'void <b>foo</b>();')


class VariableDeclarationTests(SingleFileTestCase):
    """Tests for declarations of variables"""

    source = r"""
        extern int x;
        int x = 0;
        void foo()
        {
            extern int x;
        }
        """ + MINIMAL_MAIN

    def test_variable(self):
        """Try searching for variable declarations."""
        self.found_lines_eq('var-decl:x', [
            ('extern int <b>x</b>;', 2),
            ('extern int <b>x</b>;', 6)])
