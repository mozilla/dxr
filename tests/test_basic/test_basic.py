from dxr.testing import DxrInstanceTestCase

from nose.tools import eq_, ok_


class BasicTests(DxrInstanceTestCase):
    """Tests for functionality that isn't specific to particular filters"""

    def test_text(self):
        """Assert that a plain text search works."""
        self.found_files_eq('main', ['main.c', 'makefile'])

    def test_and(self):
        """Finding 2 words should find only the lines that contain both."""
        self.found_line_eq(
            'main int',
            '<b>int</b> <b>main</b>(<b>int</b> argc, char* argv[]){',
            4)

    def test_structural_and(self):
        """Try ANDing a structural with a text filter."""
        self.found_line_eq(
            'function:main int',
            '<b>int</b> <b>main</b>(<b>int</b> argc, char* argv[]){',
            4)

    def test_case_sensitive(self):
        """Make sure case-sensitive searching is case-sensitive.

        This tests trilite's substr-extents query type.

        """
        self.found_files_eq('really',
                            ['README.mkd'],
                            is_case_sensitive=True)
        self.found_nothing('REALLY',
                           is_case_sensitive=True)

    def test_case_insensitive(self):
        """Test case-insensitive free-text searching without extents.

        Also test negation of text queries.

        This tests trilite's isubstr query type.

        """
        results = self.search_results(
            'path:makefile -CODE', is_case_sensitive=False)
        eq_(results,
            [{"path": "makefile",
              "lines": [
                {"line_number": 3,
                  "line": "$(CXX) -o $@ $^"},
                {"line_number": 4,
                  "line": "clean:"}],
              "icon": "unknown",
              "is_binary": False}])

    def test_case_insensitive_extents(self):
        """Test case-insensitive free-text searching with extents.

        This tests trilite's isubstr-extents query type.

        """
        self.found_files_eq('MAIN',
                            ['main.c', 'makefile'],
                            is_case_sensitive=False)

    def test_index(self):
        """Make sure the index controller redirects."""
        response = self.client().get('/')
        eq_(response.status_code, 302)
        ok_(response.headers['Location'].endswith('/code/source/'))

    def test_file_based_search(self):
        """Make sure searches that return files and not lines work.

        Specifically, test behavior when SearchFilter.has_lines is False.

        """
        eq_(self.search_results('path:makefile'),
            [{"path": "makefile",
              "lines": [],
              "icon": "unknown",
              "is_binary": False}])

    def test_filter_punting(self):
        """Make sure filters can opt out of filtration--in this case, due to
        terms shorter than trigrams. Make sure even opted-out filters get a
        chance to highlight.

        """
        # Test a bigram that should be highlighted and one that shouldn't.
        self.found_line_eq(
            'argc gv qq',
            'int main(int <b>argc</b>, char* ar<b>gv</b>[]){',
            4)
