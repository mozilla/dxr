from nose.tools import ok_

from dxr.testing import DxrInstanceTestCase, assert_in


class IgnorePatternTests(DxrInstanceTestCase):
    """Test for our handling of ignore_pattern"""

    def _top_level_index(self):
        """Return the HTML of the front browse page."""
        return self.client().get('/code/source/').data

    def test_non_path(self):
        """Test that non-path-based ignore patterns are obeyed."""
        html = self._top_level_index()
        assert_in('main.c', html)  # just to make sure we have the right page
        ok_('hello.h' not in html)

    def test_consecutive(self):
        """Make sure one folder being ignored doesn't accidentally eliminate
        the possibility of the next one being ignored."""
        ok_('hello2' not in self._top_level_index())

    # TODO: Test path-based ignores.
