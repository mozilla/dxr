"""Tests for contextual menu building

These integration tests guarantee that the compiler plugin is emitting the
right stuff and that that stuff makes it through the DXR clang plugin
unscathed.

"""
from dxr.testing import DxrInstanceTestCase, menu_on, menu_item_not_on
import nose.tools


class MenuTests(DxrInstanceTestCase):
    """Generally, the tests herein make sure the definition of the referenced
    thing is found (for refs) and that the qualname is extracted properly (by
    testing a representative search menuitem).

    """
    def test_includes(self):
        """Make sure #include cross references are linked."""
        menu_on(self.source_page('main.cpp'),
                '"extern.c"',
                {'html': 'Jump to file',
                 'href': '/code/source/extern.c'})

    def test_functions(self):
        """Make sure functions are found and have a representative sane menu item."""
        menu_on(self.source_page('extern.c'),
                'another_file',
                {'html': 'Find declarations',
                 'href': '/code/search?q=%2Bfunction-decl%3Aanother_file%28%29'})

    def test_function_refs(self):
        """Make sure definitions are found and a representative qualname-using
        search is properly constructed."""
        menu_on(self.source_page('main.cpp'),
                'another_file',
                {'html': 'Jump to definition',
                 'href': '/code/source/extern.c#7'},
                {'html': 'Find callers',
                 'href': '/code/search?q=%2Bcallers%3Aanother_file%28%29'})

    def test_variables(self):
        """Make sure var declarations are found and have a representative sane
        menu item."""
        menu_on(self.source_page('main.cpp'),
                'var',
                {'html': 'Find references',
                 'href': '/code/search?q=%2Bvar-ref%3Avar'})

    def test_variable_refs(self):
        """Make sure definitions are found and a representative qualname-using
        search is properly constructed."""
        menu_on(self.source_page('main.cpp'),
                'var',
                {'html': 'Jump to definition',
                 'href': '/code/source/extern.c#11'},
                {'html': 'Find declarations',
                 'href': '/code/search?q=%2Bvar-decl%3Avar'})

    def test_type(self):
        menu_on(self.source_page('extern.c'),
                'numba',
                {'html': 'Find references',
                 'href': '/code/search?q=%2Btype-ref%3Anumba'})

    def test_impl_has_sub_not_base(self):
        """Make sure a class with subclasses but not base classes gets a 'Find
        subclasses' menu option."""
        menu_on(self.source_page('extern.c'),
                'BaseClass',
                {'html': 'Find subclasses',
                 'href': '/code/search?q=%2Bderived%3ABaseClass'})

    def test_impl_no_base(self):
        """Make sure a class with subclasses but not base classes doesn't get a
        'Find base classes' menu option."""
        menu_item_not_on(self.source_page('extern.c'),
                'BaseClass',
                'Find base classes')

    def test_impl_has_sub_and_base(self):
        """Make sure a class with subclasses and base classes gets both menu
        options."""
        menu_on(self.source_page('extern.c'),
                'DerivedClass',
                {'html': 'Find subclasses',
                 'href': '/code/search?q=%2Bderived%3ADerivedClass'},
                {'html': 'Find base classes',
                 'href': '/code/search?q=%2Bbases%3ADerivedClass'})

    def test_impl_has_base_not_sub(self):
        """Make sure a class with base classes but not subclasses gets a 'Find
        base classes' menu option."""
        menu_on(self.source_page('extern.c'),
                'DerivedDerivedClass',
                {'html': 'Find base classes',
                 'href': '/code/search?q=%2Bbases%3ADerivedDerivedClass'})

    def test_impl_no_sub(self):
        """Make sure a class with base classes but not subclasses doesn't get a
        'Find subclasses' menu option."""
        menu_item_not_on(self.source_page('extern.c'),
                'DerivedDerivedClass',
                'Find subclasses')

    def test_type_ref(self):
        menu_on(self.source_page('main.cpp'),
                'MyClass',
                {'html': 'Jump to definition',
                 'href': '/code/source/extern.c#14'},
                {'html': 'Find declarations',
                 'href': '/code/search?q=%2Btype-decl%3AMyClass'})

    def test_decldef(self):
        """Make sure prototypes, declarations, and such get menus."""
        menu_on(self.source_page('extern.c'),
                'MyClass',
                {'html': 'Find references',
                 'href': '/code/search?q=%2Btype-ref%3AMyClass'})

    def test_typedef(self):
        menu_on(self.source_page('extern.c'),
                'numba',
                {'html': 'Find references',
                 'href': '/code/search?q=%2Btype-ref%3Anumba'})

    def test_typedef_ref(self):
        menu_on(self.source_page('main.cpp'),
                'numba',
                {'html': 'Jump to definition',
                 'href': '/code/source/extern.c#5'},
                {'html': 'Find references',
                 'href': '/code/search?q=%2Btype-ref%3Anumba'})

    def test_method_decl(self):
        menu_on(self.source_page('extern.c'),
                'fib',
                {'html': 'Jump to definition',
                 'href': '/code/source/extern.c#19'},
                {'html': 'Find references',
                 'href': '/code/search?q=%2Bfunction-ref%3AMyClass%3A%3Afib%28int%29'})

    def test_namespace(self):
        menu_on(self.source_page('extern.c'),
                'Space',
                {'html': 'Find definitions',
                 'href': '/code/search?q=%2Bnamespace%3ASpace'})

    def test_namespace_ref(self):
        menu_on(self.source_page('main.cpp'),
                'Space',
                {'html': 'Jump to definition',
                 'href': '/code/source/extern.c#23'},
                {'html': 'Find references',
                 'href': '/code/search?q=%2Bnamespace-ref%3ASpace'})

    def test_namespace_alias(self):
        menu_on(self.source_page('extern.c'),
                'Bar',
                {'html': 'Find references',
                 'href': '/code/search?q=%2Bnamespace-alias-ref%3ABar'})

    def test_namespace_alias_ref(self):
        menu_on(self.source_page('main.cpp'),
                'Bar',
                {'html': 'Jump to definition',
                 'href': '/code/source/extern.c#26'},
                {'html': 'Find references',
                 'href': '/code/search?q=%2Bnamespace-alias-ref%3ABar'})

    def test_macro(self):
        menu_on(self.source_page('extern.c'),
                'MACRO',
                {'html': 'Find references',
                 'href': '/code/search?q=%2Bmacro-ref%3AMACRO'})

    def test_macro_ref(self):
        menu_on(self.source_page('main.cpp'),
                'MACRO',
                {'html': 'Jump to definition',
                 'href': '/code/source/extern.c#28'},
                {'html': 'Find references',
                 'href': '/code/search?q=%2Bmacro-ref%3AMACRO'})

    def test_deep_files(self):
        """Make sure we process files not at the root level."""
        menu_on(self.source_page('deeper_folder/deeper.c'),
                'deep_thing',
                {'html': 'Find references',
                 'href': '/code/search?q=%2Btype-ref%3Adeep_thing'})

    def test_external_definition(self):
        """Things included from outside the source tree shouldn't generate
        links to their (missing) definitions."""
        menu_item_not_on(self.source_page('main.cpp'),
                         'VERY_EXTERNAL',
                         'Jump to definition')

    def test_override_overrides(self):
        """Make sure virtual functions that have an override but don't themselves
        override get a 'Find overrides' menu option."""
        menu_on(self.source_page('extern.c'),
                'virtualFunc',
                {'html': 'Find overrides',
                 'href': '/code/search?q=%2Boverrides%3ABaseClass%3A%3AvirtualFunc%28%29'})

    def test_override_no_overridden(self):
        """Make sure virtual functions that don't override don't get a 'Find overridden'
        menu option."""
        menu_item_not_on(self.source_page('extern.c'),
                'virtualFunc',
                'Find overridden')

    def test_override_overridden_and_overrides(self):
        """Make sure virtual functions that override something and are overridden
        get both menu options."""
        menu_on(self.source_page('extern.c'),
                'virtualFunc',
                {'html': 'Find overridden',
                 'href': '/code/search?q=%2Boverridden%3ADerivedClass%3A%3AvirtualFunc%28%29'},
                {'html': 'Find overrides',
                 'href': '/code/search?q=%2Boverrides%3ADerivedClass%3A%3AvirtualFunc%28%29'},
                 text_instance=2)

    def test_override_overridden(self):
        """Make sure virtual functions that override something but aren't
        themselves overridden get a 'Find overridden' menu option."""
        menu_on(self.source_page('extern.c'),
                'virtualFunc',
                {'html': 'Find overridden',
                 'href': '/code/search?q=%2Boverridden%3ADerivedDerivedClass%3A%3AvirtualFunc%28%29'},
                 text_instance=4)

    def test_override_no_overrides(self):
        """Make sure virtual functions that aren't overridden don't get a 'Find overrides'
        menu option."""
        menu_item_not_on(self.source_page('extern.c'),
                'virtualFunc',
                'Find overrides',
                text_instance=4)

    def test_override_def(self):
        """Make sure virtual function defs are recognized."""
        menu_on(self.source_page('extern.c'),
                'virtualFunc',
                {'html': 'Find overridden',
                 'href': '/code/search?q=%2Boverridden%3ADerivedClass%3A%3AvirtualFunc%28%29'},
                 text_instance=3)

    def test_override_ref(self):
        """Make sure virtual function refs are recognized."""
        menu_on(self.source_page('main.cpp'),
                'virtualFunc',
                {'html': 'Find overrides',
                 'href': '/code/search?q=%2Boverrides%3ABaseClass%3A%3AvirtualFunc%28%29'})

    def test_override_pure_overrides(self):
        """Make sure pure virtual functions that have an override are
        recognized."""
        menu_on(self.source_page('extern.c'),
                'pVirtualFunc',
                {'html': 'Find overrides',
                 'href': '/code/search?q=%2Boverrides%3ABaseClass%3A%3ApVirtualFunc%28%29'})

    def test_override_pure_overridden(self):
        """Make sure overrides of a pure virtual function are recognized."""
        menu_on(self.source_page('extern.c'),
                'pVirtualFunc',
                {'html': 'Find overridden',
                 'href': '/code/search?q=%2Boverridden%3ADerivedClass%3A%3ApVirtualFunc%28%29'},
                 text_instance=2)
