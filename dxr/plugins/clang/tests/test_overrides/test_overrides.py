"""Tests for searches about overrides of virtual methods"""

from dxr.testing import DxrInstanceTestCase
from dxr.plugins.clang.tests import CSingleFileTestCase, MINIMAL_MAIN


class ParallelOverrideTests(CSingleFileTestCase):
    """Test overrides for two classes that both directly inherit from one base
    class."""

    source = r"""
        class Base {
            virtual void foo();
        };
        void Base::foo() {
        }
        class DerivedA : public Base {
            void foo();
        };
        void DerivedA::foo() {
        }
        class DerivedB : public Base {
            void foo();
        };
        void DerivedB::foo() {
        }
        """ + MINIMAL_MAIN

    def test_overridden(self):
        self.found_line_eq(
            '+overridden:DerivedA::foo()', 'void Base::<b>foo</b>() {')
        self.found_line_eq(
            '+overridden:DerivedB::foo()', 'void Base::<b>foo</b>() {')

    def test_overrides(self):
        self.found_lines_eq('+overrides:Base::foo()',
                            [('void DerivedA::<b>foo</b>() {', 10),
                             ('void DerivedB::<b>foo</b>() {', 15)])


class HierarchyOverrideTests(CSingleFileTestCase):
    """Test overrides in a three class hierarchy."""

    source = r"""
        class Base {
            virtual void foo();
        };
        void Base::foo() {
        }
        class Derived1 : public Base {
            void foo();
        };
        void Derived1::foo() {
        }
        class Derived2 : public Derived1 {
            void foo();
        };
        void Derived2::foo() {
        }
        """ + MINIMAL_MAIN

    def test_overridden(self):
        self.found_line_eq(
            '+overridden:Derived1::foo()', 'void Base::<b>foo</b>() {')
        self.found_lines_eq('+overridden:Derived2::foo()',
                            [('void Base::<b>foo</b>() {', 5),
                             ('void Derived1::<b>foo</b>() {', 10)])

    def test_overrides(self):
        self.found_lines_eq('+overrides:Base::foo()',
                            [('void Derived1::<b>foo</b>() {', 10),
                             ('void Derived2::<b>foo</b>() {', 15)])
        # This passes:
        self.found_line_eq('+overrides:Derived1::foo()',
                           'void Derived2::<b>foo</b>() {')


class HierarchyImplicitOverrideTests(CSingleFileTestCase):
    """Test overrides in a three class hierarchy where the middle class does
    not explictly define the method."""

    source = r"""
        class Base {
            virtual void foo();
        };
        void Base::foo() {
        }
        class Derived1 : public Base {
        };
        class Derived2 : public Derived1 {
            void foo();
        };
        void Derived2::foo() {
        }
        """ + MINIMAL_MAIN

    def test_overridden(self):
        self.found_line_eq('+overridden:Derived2::foo()',
                           'void Base::<b>foo</b>() {')

    def test_overrides(self):
        self.found_line_eq('+overrides:Base::foo()',
                           'void Derived2::<b>foo</b>() {')


class MultipleOverrides(CSingleFileTestCase):
    """Test overrides when one method simultanously overrides more than one
    other method."""

    source = r"""
        class Base1 {
            virtual void foo();
        };
        void Base1::foo() {
        }
        class Base2 {
            virtual void foo();
        };
        void Base2::foo() {
        }
        class Derived : public Base1, public Base2 {
            void foo();
        };
        void Derived::foo() {
        }
        """ + MINIMAL_MAIN

    def test_overridden(self):
        self.found_lines_eq('+overridden:Derived::foo()',
                            [('void Base1::<b>foo</b>() {', 5),
                             ('void Base2::<b>foo</b>() {', 10)])

    def test_overrides1(self):
        self.found_line_eq('+overrides:Base1::foo()',
                           'void Derived::<b>foo</b>() {')

    def test_overrides2(self):
        self.found_line_eq('+overrides:Base2::foo()',
                           'void Derived::<b>foo</b>() {')


class OverrideInDifferentCompilationUnit(DxrInstanceTestCase):
    """Test overrides and overriddens when the overriding and overridden
    methods are defined in different compilation units."""

    def test_overridden(self):
        """Find parent/ancestor methods overridden by a given one."""
        self.found_line_eq(
            '+overridden:Derived::foo()', 'void Base::<b>foo</b>() {}', 3)

    def test_overrides(self):
        """Find child/descendant methods which override a given one."""
        self.found_line_eq(
            '+overrides:Base::foo()', 'void Derived::<b>foo</b>() {}', 3)
