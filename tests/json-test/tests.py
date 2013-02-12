from nose import SkipTest

from dxr.testing import DxrInstanceTestCase


class JsonTests(DxrInstanceTestCase):
    """A grab bag of tests which should be broken out into several independent,
    simpler DXR instances"""

    def test_text(self):
        """Assert that a plain text search works."""
        self.assert_query_includes('main', ['main.c', 'makefile'])

    def test_extensions(self):
        """Try search by filename extension."""
        self.assert_query_includes('ext:h', ['BitField.h', 'hello.h'])

    def test_functions(self):
        """Try searching for function declarations."""
        self.assert_query_includes('function:main', ['main.c'])
        self.assert_query_includes('function:getHello', ['hello.h'])

    def test_members(self):
        self.assert_query_includes("member:BitField", ["BitField.h"])

    def test_member_function(self):
        """Test searching for members of a class (or struct) that contains
        only member functions"""
        self.assert_query_includes("+member:MemberFunction", ["member_function.cpp"])

    def test_member_variable(self):
        """Test searching for members of a class (or struct) that contains
        only member variables"""
        self.assert_query_includes("+member:MemberVariable", ["member_variable.cpp"])

    def test_const_functions(self):
        """Make sure const functions are indexed separately from non-const but
        otherwise identical signatures."""
        self.assert_query_includes('+function:ConstOverload::foo()', ["const_overload.cpp"])
        self.assert_query_includes('+function:"ConstOverload::foo() const"', ["const_overload.cpp"])

    def test_prototype_params(self):
        self.assert_query_includes('+var:prototype_parameter_function(int)::prototype_parameter', ['prototype_parameter.cpp'])
        self.assert_query_includes('+var-ref:prototype_parameter_function(int)::prototype_parameter', ['prototype_parameter.cpp'])

    def test_static_members(self):
        self.assert_query_includes('+var:StaticMember::static_member', ['static_member.cpp'])

    def test_callers(self):
        self.assert_query_includes("callers:getHello", ["main.c"])

    def test_called_by(self):
        self.assert_query_includes("called-by:main", ["hello.h"])

    def test_typedefs(self):
        self.assert_query_includes('+type:MyTypedef', ['typedef.h'])
        self.assert_query_includes('+type-ref:MyTypedef', ['typedef.cpp'])

    def test_macro_ifdef(self):
        """Test that a macro mentioned in an #ifdef directive is treated as a
        reference"""
        self.assert_query_includes("+macro-ref:MACRO_IFDEF", ['macro_ifdef.cpp'])

    def test_macro_ifndef(self):
        """Test that a macro mentioned in an #ifndef directive is treated as a
        reference"""
        self.assert_query_includes("+macro-ref:MACRO_IFNDEF", ['macro_ifndef.cpp'])

    def test_macro_undef(self):
        """Test that a macro mentioned in an #undef directive is treated as a
        reference"""
        self.assert_query_includes("+macro-ref:MACRO_UNDEF", ['macro_undef.cpp'])

    def test_macro_if_defined(self):
        """Test that a macro mentioned in an #if defined() expression is treated
        as a reference"""
        self.assert_query_includes("+macro-ref:MACRO_IF_DEFINED", ['macro_if_defined.cpp'])
