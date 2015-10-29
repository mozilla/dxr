from nose import SkipTest

from dxr.testing import DxrInstanceTestCase

class RefFilterTests(DxrInstanceTestCase):
    """Rust plugin does some funny stuff with its needles, e.g. 'name' being an
    integer or not being present, so make sure DXR does not break.
    """

    def test_normal_name_ref(self):
        # Regular name ref, a string.
        self.found_line_eq('ref:krate', 'extern crate <b>krate</b>;', 3)

    def test_integer_name_ref(self):
        # 'name' of the needle is an integer.
        self.found_line_eq('ref:std', 'use <b>std</b>::io;', 5)

    def test_empty_name_ref(self):
        raise SkipTest("TOOD: construct a test case to find a needle without 'name'")
