import os.path

from dxr.query import Query
from dxr.utils import connect_db
from dxr.testing import SingleFileTestCase, MINIMAL_MAIN

from nose import SkipTest
from nose.tools import eq_


class DirectResultQueryTests(SingleFileTestCase):
    def direct_result_eq(self, query_text, line_num):
        conn = connect_db(os.path.join(self._config_dir_path, 'target', 'trees', 'code'))
        if line_num is None:
            eq_(Query(conn, query_text).direct_result(), None)
        else:
            eq_(Query(conn, query_text).direct_result(), ('main.cpp', line_num))


class MemberFunctionTests(DirectResultQueryTests):
    source = """
        class MemberFunction {
            public:
                void member_function(int a);        // Don't assume the qualname
                void MEMBER_FUNCTION(int a);        // field in the DB ends in just
                void unique_member_function(int a); // ().

            class InnerClass {
            };
            class INNERCLASS {
            };
            class UniqueInnerClass{
            };
        };

        void MemberFunction::member_function(int a) {
        }
        void MemberFunction::MEMBER_FUNCTION(int a) {
        }
        void MemberFunction::unique_member_function(int a) {
        }
        """ + MINIMAL_MAIN

    def test_qualified_function_name_prefix_insensitive(self):
        """A unique, case-insensitive prefix match on fully qualified function
        name should take you directly to the result"""
        self.direct_result_eq('MemberFunction::unique_member_FUNCTION', 20)

    def test_qualified_function_name_prefix_sensitive(self):
        """A unique, case-sensitive prefix match on fully qualified function
        name should take you directly to the result.

        This should have precedence over any case-insensitive match.

        """
        raise SkipTest('This does not take precedence like it should.')
        self.direct_result_eq('MemberFunction::member_function', 14)

    def test_qualified_function_name_prefix_multiple_matches(self):
        """Multiple prefix matches on fully qualified function name should
        return None."""
        self.direct_result_eq('MemberFunction::member_FUNCTION', None)

    def test_qualified_type_name_insensitive(self):
        """A unique, case-insensitive prefix match on fully qualified type
        name should take you directly to the result."""
        self.direct_result_eq('MemberFunction::uniqueinnerClass', 12)

    def test_qualified_type_name_sensitive(self):
        """A unique, case-sensitive prefix match on fully qualified type name
        should take you directly to the result.

        This should have precedence over any case-insensitive match.

        """
        raise SkipTest('This does not take precedence like it should.')
        self.direct_result_eq('MemberFunction::InnerClass', 8)

    def test_qualified_type_name_multiple_matches(self):
        """Multiple case-insensitive prefix matches on fully qualified type
        name should not yield a direct result."""
        self.direct_result_eq('MemberFunction::InnerCLASS', None)

    def test_line_number(self):
        """A file name and line number should take you directly to that file
        and line number."""
        self.direct_result_eq('main.cpp:6', 6)


class MacroTypedefTests(DirectResultQueryTests):
    source = """
        #ifndef MACRO_NAME
        #define MACRO_NAME(arg1, arg2) 0
        #endif

        #ifndef macro_name
        #define macro_name(arg1, arg2) 1
        #endif

        #ifndef UNIQUE_MACRO_NAME
        #define UNIQUE_MACRO_NAME(arg1, arg2) 2
        #endif

        typedef int MyTypeDef;
        typedef int MYTYPEDEF;
        typedef int MyUniqueTypeDef;
        """ + MINIMAL_MAIN

    def test_macro_name_insensitive(self):
        """A unique, case-insensitive match on a macro name should take you
        directly to the result."""
        self.direct_result_eq('unique_MACRO_NAME', 11)

    def test_macro_name_sensitive(self):
        """A unique, case-sensitive match on a macro name should take you
        directly to the result.

        This should have precedence over any case-insensitive match.

        """
        self.direct_result_eq('MACRO_NAME', 3)

    def test_macro_name_multiple_matches(self):
        """Multiple matches on a macro name should return None."""
        self.direct_result_eq('macro_NAME', None)

    def test_typedef_name_insensitive(self):
        """A unique, case-insensitive match on a typedef name should take you
        directly to the result."""
        self.direct_result_eq('myuniqueTypeDef', 16)

    def test_typedef_name_sensitive(self):
        """A unique, case-sensitive match on a typedef name should take you
        directly to the result.

        This should have precedence over any case-insensitive match.

        """
        self.direct_result_eq('MyTypeDef', 14)

    def test_typedef_name_multiple_matches(self):
        """Multiple matches on a typedef name should return None."""
        self.direct_result_eq('myTypeDef', None)
