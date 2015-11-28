from dxr.testing import SingleFileTestCase, DxrInstanceTestCase
import os

class RustDxrInstanceTestCase(DxrInstanceTestCase):
    @classmethod
    def setup_class(cls):
        os.environ["RUSTC"] = "rustc -Zsave-analysis"
        super(RustDxrInstanceTestCase, cls).setup_class()


class RustSingleFileTestCase(SingleFileTestCase):
    """Test case suited to testing the Rust plugin."""
    source_filename = 'mod.rs'

    @classmethod
    def config_input(cls, config_dir_path):
        config = super(RustSingleFileTestCase, cls).config_input(config_dir_path)
        
        config['DXR']['enabled_plugins'] = 'pygmentize rust'
        config['code']['build_command'] = '$RUSTC mod.rs'
        
        os.environ["RUSTC"] = "rustc -Zsave-analysis"

        return config
