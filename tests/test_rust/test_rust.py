from nose import SkipTest
from nose.tools import eq_,ok_
from dxr.testing import DxrInstanceTestCase
import os

if 'RUSTC' not in os.environ:
    raise SkipTest

class RustTests(DxrInstanceTestCase):
    """Test indexing of Rust projects"""

    def test_smoke(self):
        """Test the index exists and didn't crash."""

        response = self.client().get('/')
        eq_(response.status_code, 302)
        ok_(response.headers['Location'].endswith('/code/source/'))
