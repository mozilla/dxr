from dxr.testing import DxrInstanceTestCase
import os


class CargoTests(DxrInstanceTestCase):
    @classmethod
    def setup_class(cls):
        os.environ["RUSTC"] = "../../../dxr-rustc.sh"
        super(CargoTests, cls).setup_class()

    def test_simple_function(self):
        self.found_line_eq('function:foo', "fn <b>foo</b>() {", 1)

    def test_fn_ref(self):
        self.found_line_eq('function-ref:foo', "<b>foo</b>();", 6)
