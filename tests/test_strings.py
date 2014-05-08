"""Tests for string searches"""

from nose.tools import eq_

from dxr.extents import highlight_line
from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class StringTests(SingleFileTestCase):
    source = """
        void main_idea() {
        }
        """ + MINIMAL_MAIN

    def test_negated_word(self):
        """Make sure a negated word with underscores supresses results."""
        self.found_nothing('void -main_idea')

    def test_negated_phrase(self):
        """Make sure a negated phrase search doesn't crash."""
        self.found_line_eq('void -"int"', '<b>void</b> main_idea() {')

    def test_empty_quotes(self):
        """An effectively empty query should not filter the results at all.

        It also should not trigger the trilite bug in which empty extents
        queries hang: https://github.com/jonasfj/trilite/issues/6.

        """
        eq_(len(self.found_files('"')), 1)
        eq_(len(self.found_files('""')), 1)
        eq_(len(self.found_files('regexp:""')), 1)


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


def test_highlight_line():
    """A unit test for highlight_line() that I found handy while rewriting it

    Redundant with most of the rest of these tests but runs fast, so let's keep
    it.

    """
    source = """int main(int argc, char* argv[]) {
            return 0;
        }
        """
    eq_(highlight_line(source.splitlines()[0], [(0, 3), (9, 12)], '<b>', '</b>', 'utf-8'),
        '<b>int</b> main(<b>int</b> argc, char* argv[]) {')
