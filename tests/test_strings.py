"""Tests for string searches"""

from nose import SkipTest
from nose.tools import eq_

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
        raise SkipTest
        self.found_lines_eq('int', 
                            '<b>int</b> main(<b>int</b> argc, char* argv[]) {')
