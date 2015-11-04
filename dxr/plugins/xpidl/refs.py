from dxr.lines import Ref
from dxr.plugins.xpidl.filters import PLUGIN_NAME
from dxr.plugins.xpidl.menus import (filtered_search_menu, typedecl_menu, subclass_menu, type_menu,
                                     vardecl_menu, var_menu, function_menu, functiondecl_menu,
                                     include_menu, generated_menu)


class _XpidlRef(Ref):
    plugin = PLUGIN_NAME


class _NameMenusRef(_XpidlRef):
    """Ref class that spits out some menus for filtered searches on a given name,
    using name_menus, a sequence of (html, title, filter name, icon) tuples."""

    def menu_items(self):
        name = self.menu_data
        for html, title, filter_name, icon in self.name_menus:
            yield filtered_search_menu(self.tree, name, html, title, filter_name, icon)


class _NameMenusRefWithGenerated(_XpidlRef):
    """Uses the same name_menus scheme to generate menus as _NameMenusRef, but adds a new menu
    for jumping to the generated code."""

    def menu_items(self):
        name, generated_url, line = self.menu_data
        for html, title, filter_name, icon in self.name_menus:
            yield filtered_search_menu(self.tree, name, html, title, filter_name, icon)
        yield generated_menu(generated_url, line)


class InterfaceRef(_NameMenusRefWithGenerated):
    name_menus = [type_menu, subclass_menu]


class ForwardInterfaceRef(_NameMenusRefWithGenerated):
    name_menus = [typedecl_menu, subclass_menu]


class ExtendedInterfaceRef(_NameMenusRef):
    name_menus = [typedecl_menu, subclass_menu]


class VarMemberRef(_NameMenusRef):
    name_menus = [vardecl_menu, var_menu]


class MethodMemberRef(_NameMenusRef):
    name_menus = [functiondecl_menu, function_menu]


class TypeDefRef(_NameMenusRefWithGenerated):
    name_menus = []


class IncludeRef(_XpidlRef):
    def menu_items(self):
        resolved_path = self.menu_data
        yield include_menu(self.tree, resolved_path)
