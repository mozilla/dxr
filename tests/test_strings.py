"""Tests for string searches"""

from nose.tools import eq_

from dxr.query import _highlit_lines
from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class StringTests(SingleFileTestCase):
    source = """
        void main_idea() {
        }
        """ + MINIMAL_MAIN

    def test_negated_phrase(self):
        """Make sure a negated phrase search doesn't crash."""
        eq_(self.search_results('void -"int"'), [])


class RepeatedResultTests(SingleFileTestCase):
    # Putting code on the first line triggers the bug:
    source = """int main(int argc, char* argv[]) {
            return 0;
        }
        """

    def test_repeated_results(self):
        """Make sure we don't get the same line back twice."""
        self.found_line_eq('int',
                           '<b>int</b> main(<b>int</b> argc, char* argv[]) {')


def test_highlit_lines():
    """A unit test for _highlit_lines() that I found handy while rewriting it

    Redundant with most of the rest of these tests but runs fast, so let's keep
    it.

    """
    source = """int main(int argc, char* argv[]) {
            return 0;
        }
        """
    eq_(_highlit_lines(source, [(0, 3, []), (9, 12, [])], '<b>', '</b>'),
        [(1, '<b>int</b> main(<b>int</b> argc, char* argv[]) {')])
