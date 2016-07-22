from dxr.plugins.clang.tests import CSingleFileTestCase, MINIMAL_MAIN


class TypeAndMethodTests(CSingleFileTestCase):
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

    def test_qualified_function_name_insensitive(self):
        """A unique, case-insensitive match on fully qualified function name
        should take you directly to the result"""
        self.direct_result_eq('MemberFunction::unique_member_FUNCTION(int)', 20)

    def test_qualified_function_name_sensitive(self):
        """A unique, case-sensitive match on fully qualified function name
        should take you directly to the result.

        This should have precedence over any case-insensitive match.

        """
        self.direct_result_eq('MemberFunction::member_function(int)', 16)

    def test_scoped_function_name_insensitive(self):
        """A unique, case-insensitive match on a scoped function name should
        take you directly to the result.

        A "scoped" function name is a fully qualified one without types.

        """
        self.direct_result_eq('MemberFunction::unique_member_FUNCTION', 20)

    def test_scoped_function_name_sensitive(self):
        """A unique, case-sensitive match on scoped function name should take
        you directly to the result.

        This should have precedence over any case-insensitive match.

        """
        self.direct_result_eq('MemberFunction::member_function', 16)

    def test_qualified_function_name_multiple_matches(self):
        """Multiple matches on fully qualified function name should not yield
        a direct result."""
        self.is_not_redirect_result('MemberFunction::member_FUNCTION(int)')

    def test_qualified_type_name_insensitive(self):
        """A unique, case-insensitive match on fully qualified type name
        should take you directly to the result."""
        self.direct_result_eq('MemberFunction::uniqueinnerClass', 12)

    def test_qualified_type_name_sensitive(self):
        """A unique, case-sensitive prefix match on fully qualified type name
        should take you directly to the result.

        This should have precedence over any case-insensitive match.

        """
        self.direct_result_eq('MemberFunction::InnerClass', 8)

    def test_qualified_type_name_multiple_matches(self):
        """Multiple case-insensitive prefix matches on fully qualified type
        name should not yield a direct result."""
        self.is_not_redirect_result('MemberFunction::InnerCLASS')

    def test_type_sensitive(self):
        """If the query is an exact match for a class, we should jump there."""
        self.direct_result_eq('MemberFunction', 2)




class MacroTypedefTests(CSingleFileTestCase):
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
        """Multiple matches on a macro name should not yield a direct
        result."""
        self.is_not_redirect_result('macro_NAME')

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
        """Multiple matches on a typedef name should not yield a direct
        result."""
        self.is_not_redirect_result('myTypeDef')
