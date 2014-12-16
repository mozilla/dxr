from dxr.testing import DxrInstanceTestCase


class TestEmptyTree(DxrInstanceTestCase):
    """Tests for empty source tree"""

    def test_empty(self):
        """If it gets this far, the build didn't crash."""
