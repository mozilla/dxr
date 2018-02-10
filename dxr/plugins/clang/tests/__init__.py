from dxr.testing import SingleFileTestCase


class CSingleFileTestCase(SingleFileTestCase):
    source_filename = 'main.cpp'
    cflags = ''

    @classmethod
    def config_input(cls, config_dir_path):
        input = super(CSingleFileTestCase, cls).config_input(config_dir_path)
        input['DXR']['enabled_plugins'] = 'pygmentize clang'
        input['code']['build_command'] = '$CXX %s -c main.cpp' % cls.cflags
        return input

