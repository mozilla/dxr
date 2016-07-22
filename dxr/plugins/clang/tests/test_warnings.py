"""Tests for searches about warnings"""

from dxr.plugins.clang.tests import CSingleFileTestCase, MINIMAL_MAIN


class TautWarningTests(CSingleFileTestCase):
    """Tests for searches of a tautological comparison warning"""

    source = r"""
        void foo(unsigned int x)
        {
            if (x < 0)
                return;
        }
        """ + MINIMAL_MAIN

    def test_warning(self):
        self.found_line_eq(
            'warning:"comparison of unsigned expression < 0 is always false"',
            'if (<b>x</b> &lt; 0)')

    def test_warning_opt(self):
        self.found_line_eq(
            'warning-opt:-Wtautological-compare', 'if (<b>x</b> &lt; 0)')


class MultipleOnSameLineWarningTests(CSingleFileTestCase):
    """Tests for searches when there are multiple warnings on one line"""

    source = r"""
        void foo(int x)
        {
            if (!x < 3)
                return;
        }
        """ + MINIMAL_MAIN

    def test_warning(self):
        if self.clang_at_least(3.4):
            self.found_line_eq(
                'warning:"logical not is only applied to the left hand side of this comparison"', 'if (!x <b>&lt;</b> 3)')
        self.found_line_eq(
            'warning:"comparison of constant 3 with expression of type \'bool\' is always true"',
            'if (<b>!x</b> &lt; 3)')

    def test_warning_opt(self):
        if self.clang_at_least(3.4):
            self.found_line_eq(
                'warning-opt:-Wlogical-not-parentheses', 'if (!x <b>&lt;</b> 3)')
        self.found_line_eq(
            'warning-opt:-Wtautological-constant-out-of-range-compare', 'if (<b>!x</b> &lt; 3)')
