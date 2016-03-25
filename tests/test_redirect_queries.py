from dxr.testing import SingleFileTestCase


class DirectSearchTests(SingleFileTestCase):
    source = """
        // What happen
        // Somebody set up us the bomb
        // We get signal
        // How are you gentlemen
        // All your base
        // Are belong to us
        """

    def test_direct_line_number(self):
        """A file name and line number should take you directly to that file
        and line number."""
        self.direct_result_eq('main:6', 6)

    def test_direct_file(self):
        """A file name should take you directly to that file, without
        highlighting a particular line."""
        self.direct_result_eq('main', None)

    def test_single_line_number(self):
        """Test that a search returning a single line result takes you directly
        to that line."""
        self.single_result_eq('// We get signal', 4)

    def test_single_file(self):
        """Test that a 'path:' search returning a single file result takes you
        directly to that file."""
        self.single_result_eq('path:main', None)

    def test_multiple_results_no_redirect(self):
        """Test that we don't redirect on more than one non-direct result."""
        self.is_not_redirect_result("' us'")
