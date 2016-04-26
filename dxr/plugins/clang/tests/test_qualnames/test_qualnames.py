"""Test that the plugin returns consistent qualnames for function parameters
referenced in varying namespace environments.

"""
from urllib import quote_plus

from dxr.testing import DxrInstanceTestCase, menu_on

class ConsistencyTests(DxrInstanceTestCase):
    def _qualname_check(self, name, qualname, call_line, line):
        """Test function qualname consistency across function refs at header,
        implementation, and call sites.

        :arg name: The function's name (without namespace)
        :arg qualname: The qualname of the function as fed to 'callers:'
        :arg call_line: The expected line from the result of the 'callers:'
            search
        :arg line: The expected line number of the single result from the
            'callers:' search

        """
        callers_query = (
            '/code/search?q=%2Bcallers%3A%22{0}%22'.format(quote_plus(qualname)) if
            ' ' in qualname else
            '/code/search?q=%2Bcallers%3A{0}'.format(quote_plus(qualname)))
        # Check that the header ref uses the right qualname:
        menu_on(self.source_page('main.h'),
                name,
                {'html': 'Find callers',
                 'href': callers_query})
        # Check that the implementation ref uses the right qualname:
        menu_on(self.source_page('foo.cpp'),
                name,
                {'html': 'Find callers',
                 'href': callers_query})
        # Check that a call site uses the right qualname:
        menu_on(self.source_page('main.cpp'),
                name,
                {'html': 'Find callers',
                 'href': callers_query})
        # Check that we actually find the caller:
        self.found_line_eq('+callers:"{0}"'.format(qualname),
                            call_line,
                            line)

    def test_class_qualname_consistency(self):
        """Test consistency for a function with a class parameter."""
        self._qualname_check('f_class',
                             'f_class(bear::t_class)',
                             '<b>f_class(t_class())</b>;',
                             7)

    def test_enum_class_qualname_consistency(self):
        """Test consistency for a function with an enum class parameter."""
        self._qualname_check('f_enum_class',
                             'f_enum_class(const bear::t_enum_class *const)',
                             '<b>f_enum_class(&amp;oversized_feature)</b>;',
                             9)

    def test_template_qualname_consistency(self):
        """Test consistency for a function with a namespaced templated parameter."""
        self._qualname_check('f_template',
                             'f_template(t_template<sonic::fur>)',
                             '<b>f_template(t_template&lt;fur&gt;())</b>;',
                             10)

    def test_typedef_namespace_consisteny(self):
        """Test consistency for a namespaced function with a typedefed parameter."""
        self._qualname_check('f_typedef',
                             'sonic::f_typedef(streamOfInts)',
                             '<b>f_typedef(streamOfInts())</b>;',
                             11)
