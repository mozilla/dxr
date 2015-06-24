from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class DirectSearchTests(SingleFileTestCase):
    source = """
        // What happen
        // Somebody set up us the bomb
        // We get signal
        // How are you gentlemen
        // All your base
        // Are belong to us
        """ + MINIMAL_MAIN

    def test_line_number(self):
        """A file name and line number should take you directly to that file
        and line number."""
        self.direct_result_eq('main.cpp:6', 6)

    def test_file(self):
        """A file name should take you directly to that file, without
        highlighting a particular line."""
        self.direct_result_eq('main.cpp', None)
