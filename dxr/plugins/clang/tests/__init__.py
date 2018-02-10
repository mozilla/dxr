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


# Tests that don't otherwise need a main() can append this one just to get
# their code to compile:
MINIMAL_MAIN = """
    int main(int argc, char* argv[]) {
        return 0;
    }
    """
