from dxr.testing import SingleFileTestCase


class PythonSingleFileTestCase(SingleFileTestCase):
    """Test case suited to testing the Python plugin."""
    source_filename = 'main.py'

    @classmethod
    def config_input(cls, config_dir_path):
        config = super(PythonSingleFileTestCase, cls).config_input(config_dir_path)

        config['DXR']['enabled_plugins'] = 'pygmentize python'
        config['code']['build_command'] = ''
        config['code']['python'] = {
            'python_path': '{0}/code'.format(config_dir_path)
        }

        return config
