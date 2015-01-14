from dxr.testing import DxrInstanceTestCase

class TestEmptyTree(DxrInstanceTestCase):
    """Tests for empty source tree"""

    def test_empty(self):
        """Test empty"""
        self.found_nothing('path:*.*', is_case_sensitive=False)
