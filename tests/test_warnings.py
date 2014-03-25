"""Tests for searches about warnings"""

import commands
import re
from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class TautWarningTests(SingleFileTestCase):
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
            'warning:"* always false"', 'if (<b>x</b> &lt; 0)')

    def test_warning_opt(self):
        self.found_line_eq(
            'warning-opt:-Wtautological-compare', 'if (<b>x</b> &lt; 0)')


class MultipleOnSameLineWarningTests(SingleFileTestCase):
    """Tests for searches when there are multiple warnings on one line"""

    source = r"""
        void foo(int x)
        {
            if (!x < 3)
                return;
        }
        """ + MINIMAL_MAIN

    def _clang_at_least(self, version):
        output = commands.getoutput("clang --version")
        if not output:
            return False
        match = re.match("clang version ([0-9]+\.[0-9]+)", output[0])
        if not match:
            return False
        return float(match.group(1)) >= version

    def test_warning(self):
        if self._clang_at_least(3.4):
            self.found_line_eq(
                'warning:"logical not *"', 'if (!x <b>&lt;</b> 3)')
        self.found_line_eq(
            'warning:"* always true"', 'if (<b>!x</b> &lt; 3)')

    def test_warning_opt(self):
        if self._clang_at_least(3.4):
            self.found_line_eq(
                'warning-opt:-Wlogical-not-parentheses', 'if (!x <b>&lt;</b> 3)')
        self.found_line_eq(
            'warning-opt:-Wtautological-constant-out-of-range-compare', 'if (<b>!x</b> &lt; 3)')
