# Index a huge file containing as much of Rust as I could think of. Check that
# index finishes without crashing. This is also a good test for manual
# experimentation.

from dxr.plugins.rust.tests import RustDxrInstanceTestCase


class RustTests(RustDxrInstanceTestCase):
    """Test indexing of Rust projects"""

    def test_nothing(self):
        """A null test just to make the setup method run"""
