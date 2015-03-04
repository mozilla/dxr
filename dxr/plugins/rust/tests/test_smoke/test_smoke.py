# Index a huge file containing as much of Rust as I could think of. Check that
# index finishes without crashing. This is also a good test for manual
# experimentation.

from nose import SkipTest
from nose.tools import eq_,ok_
from dxr.testing import DxrInstanceTestCase
import os

# We'll also need rust libs to be in LD_LIBRARY_PATH, but there's not an easy
# way to test for that.
if 'RUSTC' not in os.environ:
    raise SkipTest

class RustTests(DxrInstanceTestCase):
    """Test indexing of Rust projects"""

    def test_smoke(self):
        """Test the index exists and didn't crash."""

        response = self.client().get('/')
        eq_(response.status_code, 302)
        ok_(response.headers['Location'].endswith('/code/source/'))
