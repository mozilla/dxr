"""Tests for string searches"""

from nose.tools import eq_

from dxr.extents import highlight
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


def test_highlight():
    """Try ``highlight()`` against overlapping and disjunct inputs."""
    eq_(highlight('inini main(ini argc, char* argv[]) {',
                  [(0, 3), (2, 5), (11, 14)]),
        '<b>in</b><b>i</b><b>ni</b> main(<b>ini</b> argc, char* argv[]) {')
    # That's not the optimal result, but it's a correct one.


class RegexpTests(SingleFileTestCase):
    """Tests for the registration and flow of the RegexpFilter itself.

    test_trigrammer tests the bazillion corner cases of regex translation.

    """
    source = """// Which of us is the beaver?
        // The paddle-shaped tail is a dead giveaway.
        // We know it's you, Shahad.
        """ + MINIMAL_MAIN

    def test_case_sensitive(self):
        self.found_line_eq('regexp:" ?The ?"',
                           '//<b> The </b>paddle-shaped tail is a dead giveaway.',
                           is_case_sensitive=True)

    def test_case_insensitive(self):
        self.found_lines_eq(
            'regexp:sha[a-z]+d',
            [('// The paddle-<b>shaped</b> tail is a dead giveaway.', 2),
             ("// We know it's you, <b>Shahad</b>.", 3)],
            is_case_sensitive=False)
