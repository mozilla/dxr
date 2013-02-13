from nose import SkipTest

from dxr.testing import DxrInstanceTestCase


class JsonTests(DxrInstanceTestCase):
    """A grab bag of tests which should be broken out into several independent,
    simpler DXR instances"""

    def test_text(self):
        """Assert that a plain text search works."""
        self.found_files_eq('main', ['main.c', 'makefile'])

    def test_extensions(self):
        """Try search by filename extension."""
        self.found_files_eq('ext:h', ['const_overload.h', 'prototype_parameter.h', 'static_member.h', 'BitField.h', 'typedef.h'])

    def test_members(self):
        self.found_files_eq("member:BitField", ["BitField.h"])

    def test_member_function(self):
        """Test searching for members of a class (or struct) that contains
        only member functions"""
        self.found_files_eq("+member:MemberFunction", ["member_function.cpp"])

    def test_member_variable(self):
        """Test searching for members of a class (or struct) that contains
        only member variables"""
        self.found_files_eq("+member:MemberVariable", ["member_variable.cpp"])

    def test_const_functions(self):
        """Make sure const functions are indexed separately from non-const but
        otherwise identical signatures."""
        self.found_files_eq('+function:ConstOverload::foo()', ["const_overload.cpp"])
        self.found_files_eq('+function:"ConstOverload::foo() const"', ["const_overload.cpp"])

    def test_prototype_params(self):
        self.found_files_eq('+var:prototype_parameter_function(int)::prototype_parameter', ['prototype_parameter.cpp'])
        self.found_files_eq('+var-ref:prototype_parameter_function(int)::prototype_parameter', ['prototype_parameter.cpp'])

    def test_static_members(self):
        self.found_files_eq('+var:StaticMember::static_member', ['static_member.cpp'])

    def test_typedefs(self):
        self.found_files_eq('+type:MyTypedef', ['typedef.h'])
        self.found_files_eq('+type-ref:MyTypedef', ['typedef.cpp'])

    def test_macro_ifdef(self):
        """Test that a macro mentioned in an #ifdef directive is treated as a
        reference"""
        self.found_files_eq("+macro-ref:MACRO_IFDEF", ['macro_ifdef.cpp'])

    def test_macro_ifndef(self):
        """Test that a macro mentioned in an #ifndef directive is treated as a
        reference"""
        self.found_files_eq("+macro-ref:MACRO_IFNDEF", ['macro_ifndef.cpp'])

    def test_macro_undef(self):
        """Test that a macro mentioned in an #undef directive is treated as a
        reference"""
        self.found_files_eq("+macro-ref:MACRO_UNDEF", ['macro_undef.cpp'])

    def test_macro_if_defined(self):
        """Test that a macro mentioned in an #if defined() expression is treated
        as a reference"""
        self.found_files_eq("+macro-ref:MACRO_IF_DEFINED", ['macro_if_defined.cpp'])
