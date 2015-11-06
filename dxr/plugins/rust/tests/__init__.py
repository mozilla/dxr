from dxr.testing import SingleFileTestCase

class RustSingleFileTestCase(SingleFileTestCase):
    """Test case suited to testing the Rust plugin."""
    source_filename = 'mod.rs'

    @classmethod
    def config_input(cls, config_dir_path):
        config = super(RustSingleFileTestCase, cls).config_input(config_dir_path)

        config['DXR']['enabled_plugins'] = 'pygmentize rust'
        config['code']['build_command'] = '$RUSTC mod.rs'

        return config
