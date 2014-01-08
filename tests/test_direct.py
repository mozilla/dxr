import os.path

from dxr.query import Query
from dxr.server_utils import connect_db
from dxr.testing import SingleFileTestCase, MINIMAL_MAIN

from nose.tools import eq_


class MemberFunctionTests(SingleFileTestCase):
    source = """
        class MemberFunction {
            public:
                void member_function(int a);  // Don't assume the qualname
                                              // field in the DB ends in just
                                              // ().

            class InnerClass {
            };
        };

        void MemberFunction::member_function(int a) {
        }
        """ + MINIMAL_MAIN

    def direct_result_eq(self, query_text, line_num):
        conn = connect_db(
            'code', os.path.join(self._config_dir_path, 'target'))
        eq_(Query(conn, query_text).direct_result(), ('main.cpp', line_num))

    def test_qualified_function_name_prefix(self):
        """A unique, case-insensitive prefix match on fully qualified function
        name should take you directly to the result."""
        self.direct_result_eq('MemberFunction::member_FUNCTION', 12)

    def test_qualified_type_name(self):
        """A unique, case-insensitive prefix match on fully qualified type name
        should take you directly to the result."""
        self.direct_result_eq('MemberFunction::InnerCLASS', 8)

    def test_line_number(self):
        """A file name and line number should take you directly to that
           file and line number."""
        self.direct_result_eq('main.cpp:6', 6)
        