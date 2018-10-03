"""Tests for searches about warnings"""

from dxr.plugins.clang.tests import CSingleFileTestCase


class TautWarningTests(CSingleFileTestCase):
    """Tests for searches of a tautological comparison warning"""

    cflags = '-Weverything'

    source = r"""
        void foo(unsigned int x)
        {
            if (x < 0)
                return;
        }
        """

    def test_warning(self):
        if self.clang_at_least(6.0):
            warning_message = "result of comparison of unsigned expression < 0 is always false"
        else:
            warning_message = "comparison of unsigned expression < 0 is always false"
        self.found_line_eq(
            'warning:"%s"' % (warning_message,),
            'if (<b>x</b> &lt; 0)')

    def test_warning_opt(self):
        if self.clang_at_least(6.0):
            warning_option = '-Wtautological-unsigned-zero-compare'
        else:
            warning_option = '-Wtautological-compare'
        self.found_line_eq(
            'warning-opt:' + warning_option, 'if (<b>x</b> &lt; 0)')


class MultipleOnSameLineWarningTests(CSingleFileTestCase):
    """Tests for searches when there are multiple warnings on one line"""

    cflags = '-Weverything'

    source = r"""
        void foo(int x)
        {
            if (!x < 3)
                return;
        }
        """

    def test_warning(self):
        if self.clang_at_least(3.4):
            self.found_line_eq(
                'warning:"logical not is only applied to the left hand side of this comparison"', 'if (!x <b>&lt;</b> 3)')
        if self.clang_at_least(6.0):
            warning_message = "result of comparison of constant 3 with expression of type 'bool' is always true"
        else:
            warning_message = "comparison of constant 3 with expression of type 'bool' is always true"
        self.found_line_eq(
            'warning:"%s"' % (warning_message,),
            'if (<b>!x</b> &lt; 3)')

    def test_warning_opt(self):
        if self.clang_at_least(3.4):
            self.found_line_eq(
                'warning-opt:-Wlogical-not-parentheses', 'if (!x <b>&lt;</b> 3)')
        self.found_line_eq(
            'warning-opt:-Wtautological-constant-out-of-range-compare', 'if (<b>!x</b> &lt; 3)')
