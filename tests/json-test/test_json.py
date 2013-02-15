from dxr.testing import DxrInstanceTestCase


class JsonTests(DxrInstanceTestCase):
    """A grab bag of tests which should be broken out into several independent,
    simpler DXR instances"""

    def test_text(self):
        """Assert that a plain text search works."""
        self.found_files_eq('main', ['main.c', 'makefile'])

    def test_extensions(self):
        """Try search by filename extension."""
        self.found_files_eq('ext:h', ['prototype_parameter.h', 'typedef.h'])

    def test_prototype_params(self):
        self.found_files_eq('+var:prototype_parameter_function(int)::prototype_parameter', ['prototype_parameter.cpp'])
        self.found_files_eq('+var-ref:prototype_parameter_function(int)::prototype_parameter', ['prototype_parameter.cpp'])

    def test_typedefs(self):
        self.found_files_eq('+type:MyTypedef', ['typedef.h'])
        self.found_files_eq('+type-ref:MyTypedef', ['typedef.cpp'])
