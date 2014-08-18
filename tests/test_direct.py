import os.path

from dxr.query import Query
from dxr.utils import connect_db
from dxr.testing import SingleFileTestCase, MINIMAL_MAIN

from nose.tools import eq_


class MemberFunctionTests(SingleFileTestCase):
    source = """
        class MemberFunction {
            public:
                void member_function(int a);  // Don't assume the qualname
                void MEMBER_FUNCTION(int a);  // field in the DB ends in just
                                              // ().

            class InnerClass {
            };
            class INNERCLASS {
            };
        };

        void MemberFunction::member_function(int a) {
        }
        void MemberFunction::MEMBER_FUNCTION(int a) {
        }
        """ + MINIMAL_MAIN

    def direct_result_eq(self, query_text, line_num):
        conn = connect_db(os.path.join(self._config_dir_path, 'target', 'trees', 'code'))
        eq_(Query(conn, query_text).direct_result(), ('main.cpp', line_num))

    def test_qualified_function_name_prefix(self):
        """A unique, case-insensitive prefix match on fully qualified function
        name should take you directly to the result."""
        self.direct_result_eq('MemberFunction::member_FUNCTION', 14)

    def test_qualified_function_name_prefix_sensitive(self):
        """A unique, case-sensitive prefix match on fully qualified function
        name should take you directly to the result. This should have precedence over
        any case-insensitive match"""
        self.direct_result_eq('MemberFunction::MEMBER_FUNCTION', 16)

    def test_qualified_type_name(self):
        """A unique, case-insensitive prefix match on fully qualified type name
        should take you directly to the result."""
        self.direct_result_eq('MemberFunction::InnerCLASS', 8)

    def test_qualified_type_name_sensitive(self):
        """A unique, case-sensitive prefix match on fully qualified type
        name should take you directly to the result. This should have precedence over
        any case-insensitive match"""
        self.direct_result_eq('MemberFunction::INNERCLASS', 10)

    def test_line_number(self):
        """A file name and line number should take you directly to that
           file and line number."""
        self.direct_result_eq('main.cpp:6', 6)


class MacroTypedefTests(MemberFunctionTests):
    source = """
        #ifdef MACRO_NAME
        #define MACRO_NAME(arg1, arg2) 0
        //#endif
        typedef int MyTypedef;
        void my_typedef_function(MyTypedef i) {
        }
        """ + MINIMAL_MAIN
    
    def test_macro_name(self):
        """An unique, case-insensitive match on a macro name should take you
           directly to the result"""
        self.direct_result_eq('MACRO_name', 3)

    def test_typedef_name(self):
        """An unique, case-insensitive match on a typedef name should take you
           directly to the result"""
        self.direct_result_eq('MyTypedef', 5)        