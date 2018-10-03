from dxr.plugins.clang.tests import CSingleFileTestCase


class UserDefinedLiteralTests(CSingleFileTestCase):
    cflags = '-std=c++11'

    source = """
        int operator "" _i(const char *) { return 0; }

        int main() {
          42_i;
          return 0;
        }
        """

    def test_def(self):
        self.found_line_eq('+function:"operator""_i(const char *)"',
            'int <b>operator "" _i</b>(const char *) { return 0; }')

    def test_ref(self):
        self.found_line_eq('+function-ref:"operator""_i(const char *)"',
            '42<b>_i</b>;')

