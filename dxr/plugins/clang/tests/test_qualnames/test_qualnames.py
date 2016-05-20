"""Test that the plugin returns consistent qualnames for function parameters
referenced in varying namespace and template environments."""

from urllib import quote_plus

from dxr.testing import DxrInstanceTestCase, menu_on

def callers_query(qualname):
    if ' ' in qualname:
        return '/code/search?q=%2Bcallers%3A%22{0}%22'.format(quote_plus(qualname))
    else:
        return '/code/search?q=%2Bcallers%3A{0}'.format(quote_plus(qualname))


class ConsistencyTests(DxrInstanceTestCase):
    def _qualname_check(self, name, qualname, content, line):
        """Test function qualname consistency across function refs at header,
        implementation, and call sites.

        :arg name: The function's name (without namespace)
        :arg qualname: The qualname of the function as fed to 'callers:'
        :arg content: The expected line of text from the result of the 'callers:'
            search
        :arg line: The expected line number of the single result from the
            'callers:' search

        """
        query = callers_query(qualname)
        # Check that the header ref uses the right qualname:
        menu_on(self.source_page('foo.h'),
                name,
                {'html': 'Find callers',
                 'href': query})
        # Check that the implementation ref uses the right qualname:
        menu_on(self.source_page('foo.cpp'),
                name,
                {'html': 'Find callers',
                 'href': query})
        # Check that a call site uses the right qualname:
        menu_on(self.source_page('main.cpp'),
                name,
                {'html': 'Find callers',
                 'href': query})
        # Check that we actually find the caller:
        self.found_line_eq('+callers:"{0}"'.format(qualname),
                            content,
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

    def test_bool_qualname_consistency(self):
        """Test that we're using 'bool' instead of '_Bool' for all of our
        bool parameter names."""
        self._qualname_check('f_bool',
                             'f_bool(bool)',
                             '<b>f_bool(true)</b>;',
                             12)

    # Template instantiation and specialization qualname checks:

    def _qualname_instances(self, name, qualname,
                            header_instances, impl_instances):
        """Test that the 'Find callers' menu item at each listed header and
        implementation instance of name has the correct '+callers:' query.

        """
        query = callers_query(qualname)
        header_page = self.source_page('template_foo.h')
        impl_page = self.source_page('template_foo.cpp')
        for header_instance in header_instances:
            # Check that the header ref uses the right qualname:
            menu_on(header_page,
                    name,
                    {'html': 'Find callers',
                    'href': query},
                    text_instance=header_instance)
        for impl_instance in impl_instances:
            # Check that the implementation ref uses the right qualname:
            menu_on(impl_page,
                    name,
                    {'html': 'Find callers',
                    'href': query},
                    text_instance=impl_instance)

    def _callers_check(self, qualname, lines):
        self.found_lines_eq('+callers:"{0}"'.format(qualname), lines)

    def test_template_function(self):
        """Test consistency for a templated function and a full specialization."""
        base_qualname = 'fud(T)'
        self._qualname_instances('fud', base_qualname, [1], [1, 2])
        self._callers_check(base_qualname, [('<b>fud(Baz&lt;int&gt;())</b>;', 7),
                                            ('<b>fud(aa)</b>;', 8)])

        # The full specialization gets its own qualname (for now):
        spec_qualname = 'fud(int)'
        self._qualname_instances('fud', spec_qualname, [2], [3])
        self._callers_check(spec_qualname, [('<b>fud(3)</b>;', 9)])

    def test_templated_parameter(self):
        """Test consistency for a templated function where a function parameter
        is itself templated."""
        qualname = 'guz(Baz<T>)'
        self._qualname_instances('guz', qualname, [1], [1])
        self._callers_check(qualname, [('<b>guz(bb)</b>;', 12)])

    def test_templated_method(self):
        """Test consistency for a templated function of a class and a full
        specialization."""
        base_qualname = 'Gub::bug(T)'
        self._qualname_instances('bug', base_qualname, [1], [1])
        self._callers_check(base_qualname, [('<b>gg.bug(2)</b>;', 15)])

        # The full specialization gets its own qualname (for now):
        spec_qualname = 'Gub::bug(char)'
        self._qualname_instances('bug', spec_qualname, [2], [2])
        self._callers_check(spec_qualname, [('<b>gg.bug(aa)</b>;', 16)])

    def test_templated_method_of_templated_class(self):
        """Test consistency for a templated method of a templated class and a
        full specialization."""
        base_qualname = 'Gleb::lerb(U)'
        self._qualname_instances('lerb', base_qualname, [1], [1])
        self._callers_check(base_qualname, [('<b>gl.lerb(true)</b>;', 19)])

        # The full specialization gets its own qualname (for now):
        spec_qualname = 'Gleb<char>::lerb(int)'
        self._qualname_instances('lerb', spec_qualname, [2], [2])
        self._callers_check(spec_qualname, [('<b>gl.lerb(3)</b>;', 20)])

    def test_partial_specialization(self):
        """Test consistency for a templated class and a partial specialization."""
        base_qualname = 'Derb::flarb(T)'
        self._qualname_instances('flarb', base_qualname, [1], [1])
        self._callers_check(base_qualname, [('<b>cc.flarb(3)</b>;', 23)])

        # The partial specialization gets its own qualname (for now):
        spec_qualname = 'Derb<type-parameter-0-0 *>::flarb(T *)'  # (ouch)
        self._qualname_instances('flarb', spec_qualname, [2], [2])
        self._callers_check(spec_qualname, [('<b>dd.flarb(&amp;aa)</b>;', 25)])
