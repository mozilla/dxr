from dxr.testing import DxrInstanceTestCase

from nose.tools import eq_, raises

class ResultsHighlightingTests(DxrInstanceTestCase):
    """Tests highlighting in search results"""

    def _found_highlit_path_eq(self, query, highlit_seg_list):
        """Test that ``query`` returns exactly one result and that the returned
        highlit path segments list matches ``highlit_seg_list``

        """
        results = self.search_results(query)
        num_results = len(results)
        eq_(num_results, 1, msg='Query passed to found_highlit_path_eq() '
                                'returned %s files, not one.' % num_results)
        result_seg_list = results[0]["path_data"]["highlit_path_segs"]
        eq_(result_seg_list, highlit_seg_list)

    def test_combined_highlighting(self):
        """Test highlighting combined file and line results, multiple extents
        in a given path segment or line, and two matches back to back.

        """
        query = "path:abc abc"
        self._found_highlit_path_eq(query,
                                    ["<b>abc</b>", "<b>abcabc</b>.<b>abc</b>"])
        self.found_line_eq(query, "<b>abc</b>, <b>abcabc</b>s", 1)

    def test_highlighting_path_across_a_slash(self):
        """Test highlighting a path across path separators ('/')"""
        # Query term spans one separator:
        self._found_highlit_path_eq("path:c/a",
                                    ["ab<b>c</b>", "<b>a</b>bcabc.abc"])

        # Query term spans two separators:
        self._found_highlit_path_eq("path:c/def/d",
                                    ["ab<b>c</b>", "<b>def</b>",
                                     "<b>d</b>ir_not_empty"])

    def test_highlighting_no_path_separators(self):
        """Test highlighting when there are no path separators in the path"""
        self._found_highlit_path_eq("path:o_se", ["n<b>o_se</b>p"])

    def test_unhighlit_path_segment(self):
        """Test that path segments that don't match the query are not highlit"""
        self._found_highlit_path_eq("path:empty",
                                    ["abc", "def", "dir_not_<b>empty</b>"])

    @raises(AssertionError) # remove this line when fixed
    def test_highlighting_path_wildcard_matches(self):
        """Test that path queries containing wildcards have their results
        properly highlit

        """
        self._found_highlit_path_eq("path:abc*.abc",
                                    ["<b>abc</b>", "<b>abcabc.abc</b>"])

    def test_extension_highlighting(self):
        """Test that matching extensions (and nothing else) are highlit in
         ``ext:`` queries

        """
        self._found_highlit_path_eq("ext:abc", ["abc", "abcabc.<b>abc</b>"])
