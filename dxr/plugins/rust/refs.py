from warnings import warn

from dxr.lines import Ref
# import ALL THE THINGS
from dxr.plugins.rust.menu import (
    jump_to_target_from_decl, jump_to_definition_menu,
    jump_to_trait_method_menu, function_menu_generic, variable_menu_generic, truncate_value,
    type_menu_generic, jump_to_module_definition_menu, module_menu_generic,
    jump_to_alias_definition_menu, jump_to_crate_menu, find_references_menu, std_lib_links,
    jump_to_module_declaration_menu, jump_to_type_declaration_menu,
    jump_to_variable_declaration_menu, jump_to_function_declaration_menu, trait_impl_menu)


def trim_dict(dictionary, keys):
    """Return a new dict with given keys set from dictionary arg.

    A key listed in keys but not in the dictionary will be set to None.
    """

    return dict((key, dictionary.get(key)) for key in keys)


class _RustRef(Ref):
    plugin = 'rust'

    def __init__(self, tree_index, menu_data, tree_config, hover=None, qualname=None, qualname_hash=None):
        super(_RustRef, self).__init__(tree_config, menu_data, hover, qualname, qualname_hash)


class _KeysFromDatum(_RustRef):
    """A Ref superclass that only holds onto certain keys of a datum dict.

    :classvar keys: a list of dict keys which will be kept in the data to pass to ES.
    """

    def __init__(self, tree_index, datum, tree_config, hover=None, qualname=None, qualname_hash=None):
        super(_KeysFromDatum, self).__init__(tree_index, None, tree_config, hover, qualname, qualname_hash)
        self.menu_data = trim_dict(datum, self.keys)


class FunctionRef(_RustRef):
    def __init__(self, tree_index, datum, tree_config):
        super(FunctionRef, self).__init__(tree_index, None, tree_config)
        if 'declid' in datum and datum['declid'] in tree_index.data.functions:
            # It's an implementation; find the decl:
            decl = tree_index.data.functions[datum['declid']]
            self.menu_data = [trim_dict(datum, ['qualname']),
                              trim_dict(decl, ['file_name', 'file_line']),
                              0]
        else:
            # It's a decl; find implementations:
            impls = tree_index.data.index('functions', 'declid')
            count = len(impls[datum['id']]) if datum['id'] in impls else 0
            self.menu_data = [trim_dict(datum, ['qualname']), None, count]

    def menu_items(self):
        # decl is only defined if datum is not a decl (i.e. we're looking at an impl).
        datum, decl, count = self.menu_data
        menus = function_menu_generic(datum, self.tree)
        if decl:
            menus.append(jump_to_target_from_decl(jump_to_trait_method_menu, self.tree, decl))
        elif count:
            menus.append(trait_impl_menu(self.tree, datum['qualname'], count))
        return menus


class FunctionRefRef(_RustRef):
    """A Ref with menus suitable to a function reference."""

    def __init__(self, tree_index, datum, tree_config):
        super(FunctionRefRef, self).__init__(tree_index, None, tree_config)

        fn_def = None
        fn_decl = None
        if 'refid' in datum and datum['refid'] and datum['refid'] in tree_index.data.functions:
            fn_def = tree_index.data.functions[datum['refid']]
        elif 'refid' in datum and datum['refid'] and datum['refid'] in tree_index.data.types:
            # enum variant ctors
            fn_def = tree_index.data.types[datum['refid']]
        if 'declid' in datum and datum['declid'] and datum['declid'] in tree_index.data.functions:
            fn_decl = tree_index.data.functions[datum['declid']]

        name = None
        if fn_def:
            name = fn_def['qualname']
        elif fn_decl:
            name = fn_decl['qualname']

        # FIXME(#12) should have type, not name for title
        self.hover = name

        data_keys = ['file_name', 'file_line', 'qualname']
        self.menu_items = [trim_dict(fn_def, data_keys), trim_dict(fn_decl, data_keys)]

    def menu_items(self):
        fn_def, fn_decl = self.menu_data
        menus = []
        if fn_def:
            menus.append(jump_to_target_from_decl(jump_to_definition_menu, self.tree, fn_def))
            if fn_decl and (fn_def['file_name'] != fn_decl['file_name'] or fn_def['file_line'] != fn_decl['file_line']):
                menus.append(jump_to_target_from_decl(jump_to_trait_method_menu, self.tree, fn_decl))
            menus.extend(function_menu_generic(fn_def, self.tree))
        elif fn_decl:
            menus = function_menu_generic(fn_decl, self.tree)
            menus.append(jump_to_target_from_decl(jump_to_trait_method_menu, self.tree, fn_decl))
        return menus


class VariableRef(_KeysFromDatum):
    keys = ['type', 'qualname']

    def __init__(self, tree_index, datum, tree_config):
        super(VariableRef, self).__init__(tree_index, datum, tree_config)
        self.hover = truncate_value("", datum.get('type'))

    def menu_items(self):
        menu = variable_menu_generic(self.menu_data, self.tree)
        typ = self.menu_data.get('type')
        qualname = self.menu_data.get('qualname')
        if not typ:
            warn("no type for variable %s" % qualname)
        return menu


class VariableRefRef(_RustRef):
    def __init__(self, tree_index, datum, tree_config):
        super(VariableRefRef, self).__init__(tree_index, None, tree_config)
        if datum['refid'] and datum['refid'] in tree_index.data.variables:
            var = tree_index.data.variables[datum['refid']]
            typ = None
            if 'type' in var:
                typ = var['type']
            else:
                warn("no type for variable ref %s" % (var['qualname'],))
            self.hover = truncate_value(typ, var['value'])
            self.menu_data = trim_dict(datum, ['file_line', 'file_name', 'qualname'])
        # TODO what is the culprit here?
        # print "variable ref missing def"

    def menu_items(self):
        if self.menu_data:
            makers = [jump_to_target_from_decl(jump_to_definition_menu, self.tree, self.menu_data)]
            makers.extend(variable_menu_generic(self.menu_data, self.tree))
            return makers


class TypeRef(_KeysFromDatum):
    keys = ['kind', 'qualname']

    def menu_items(self):
        return type_menu_generic(self.menu_data, self.tree)


class TypeRefRef(_RustRef):
    def __init__(self, tree_index, datum, tree_config):
        super(TypeRefRef, self).__init__(tree_index, None, tree_config)
        if datum['refid'] and datum['refid'] in tree_index.data.types:
            typ = tree_index.data.types[datum['refid']]
            title = None
            if 'value' in typ:
                title = typ['value']
            else:
                warn('no value for %s %s' % (typ['kind'], typ['qualname']))
            self.hover = truncate_value("", title)
            self.menu_data = trim_dict(datum, ['file_line', 'file_name', 'qualname', 'kind'])

    def menu_items(self):
        if self.menu_data:
            makers = [jump_to_target_from_decl(jump_to_definition_menu, self.tree, self.menu_data)]
            makers.extend(type_menu_generic(self.menu_data, self.tree))
            return makers


class ModuleRef(_KeysFromDatum):
    keys = ['def_file', 'file_name', 'file_line']

    def menu_items(self):
        if self.menu_data['def_file'] != self.menu_data['file_name']:
            yield jump_to_module_definition_menu(self.tree, self.menu_data['def_file'], 1)


# TODO next: turn to class
def module_ref_menu(tree, datum, tree_config):
    # Add straightforward aliases to modules
    if datum['refid']:
        makers = []
        mod = None
        if datum['refid'] in tree.data.modules:
            mod = tree.data.modules[datum['refid']]
        elif datum['refid'] in tree.data.extern_crate_mods:
            mod = tree.data.extern_crate_mods[datum['refid']]

        if mod:
            if datum['aliasid'] and datum['aliasid'] in tree.data.module_aliases:
                alias = tree.data.module_aliases[datum['aliasid']]
                if 'file_name' in mod:
                    makers.append(jump_to_target_from_decl(jump_to_alias_definition_menu, tree_config, mod))
                if 'location' in alias and alias['location'] in tree.crates_by_name:
                    # Add references to extern mods via aliases (known local crates)
                    crate = tree.crates_by_name[alias['location']]
                    makers.append(jump_to_crate_menu(tree_config, crate['file_name'], 1))
                    makers.append(find_references_menu(tree_config, alias['qualname'], "module-alias-ref", "alias"))
                elif 'location' in alias and alias['location'] in tree.locations:
                    # Add references to extern mods via aliases (standard library crates)
                    urls = tree.locations[alias['location']]
                    makers = [find_references_menu(tree_config, alias['qualname'], "module-alias-ref", "alias")]
                    std_lib_links(makers, urls)
                elif 'location' in alias:
                    # Add references to extern mods via aliases (unknown local crates)
                    makers = [find_references_menu(tree_config, alias['qualname'], "module-alias-ref", "alias")]
                elif 'file_name' in mod:
                    makers.append(jump_to_target_from_decl(jump_to_module_definition_menu, tree_config, mod))
            else:
                if 'file_name' in mod and 'def_file' in mod and mod['def_file'] == mod['file_name']:
                    makers.append(jump_to_target_from_decl(jump_to_definition_menu, tree_config, mod))
                else:
                    makers.append(jump_to_module_definition_menu(tree_config, mod['def_file'], 1))
                    makers.append(jump_to_target_from_decl(jump_to_module_declaration_menu, tree_config, mod))
            makers.extend(module_menu_generic(tree, mod, tree_config))
            return Ref(makers)

        # types masquerading as modules
        if datum['refid'] in tree.data.types:
            typ = tree.data.types[datum['refid']]
            makers = [jump_to_target_from_decl(jump_to_definition_menu, tree_config, typ)]
            makers.extend(type_menu_generic(typ, tree_config))
            title = None
            if 'value' in typ:
                title = typ['value']
            else:
                warn('no value for %s %s' % (typ['kind'], typ['qualname']))
            return Ref(makers, hover=truncate_value('', title))


# TODO next: turn to class
def module_alias_menu(tree, datum, tree_config):
    # Add straightforward aliases to modules
    if datum['refid'] and datum['refid'] in tree.data.modules:
        mod = tree.data.modules[datum['refid']]
        if mod['name'] != datum['name']:
            # Add module aliases. 'use' without an explicit alias and without any wildcards,
            # etc. introduces an implicit alias for the module. E.g, |use a::b::c|
            # introduces an alias |c|. In these cases, we make the alias transparent -
            # there is no link for the alias, but we add the alias menu stuff to the
            # module ref.
            makers = [jump_to_module_definition_menu(tree_config, mod['def_file'], 1),
                      find_references_menu(tree_config, datum['qualname'], "module-alias-ref", "alias")]
            return Ref(makers)

    # 'module' aliases to types
    if datum['refid'] and datum['refid'] in tree.data.types:
        typ = tree.data.types[datum['refid']]
        if typ['name'] != datum['name']:
            makers = [jump_to_target_from_decl(jump_to_type_declaration_menu, tree_config, typ),
                      find_references_menu(tree_config, datum['qualname'], "type-ref", "alias")]
            return Ref(makers)

    # 'module' aliases to variables
    if datum['refid'] and datum['refid'] in tree.data.variables:
        var = tree.data.variables[datum['refid']]
        if var['name'] != datum['name']:
            makers = [jump_to_target_from_decl(jump_to_variable_declaration_menu, tree_config, var),
                      find_references_menu(tree_config, datum['qualname'], "var-ref", "alias")]
            return Ref(makers)

    # 'module' aliases to functions
    if datum['refid'] and datum['refid'] in tree.data.functions:
        fn = tree.data.functions[datum['refid']]
        if fn['name'] != datum['name']:
            makers = [jump_to_target_from_decl(jump_to_function_declaration_menu, tree_config, fn),
                      find_references_menu(tree_config, datum['qualname'], "function-ref", "alias")]
            return Ref(makers)

    # extern crates to known local crates
    if 'location' in datum and datum['location'] and datum['location'] in tree.crates_by_name:
        crate = tree.crates_by_name[datum['location']]
        makers = [jump_to_crate_menu(tree_config, crate['file_name'], 1),
                  find_references_menu(tree_config, datum['qualname'], "module-alias-ref", "alias")]
        return Ref(makers)

    # extern crates to standard library crates
    if 'location' in datum and datum['location'] and datum['location'] in tree.locations:
        urls = tree.locations[datum['location']]
        menu = [find_references_menu(tree_config, datum['qualname'], "module-alias-ref", "alias")]
        std_lib_links(menu, urls)
        return Ref(menu)

    # other references to standard library items
    if datum['refid'] in tree.data.unknowns:
        # FIXME We could probably do better and link to the precise type or static in docs etc., rather than just the crate
        urls = tree.locations[tree.data.unknowns[datum['refid']]['crate']]
        menu = [find_references_menu(tree_config, datum['qualname'], "module-alias-ref", "alias")]
        std_lib_links(menu, urls)
        return Ref(menu)

    # extern mods to unknown local crates
    menu = [find_references_menu(tree_config, datum['qualname'], "module-alias-ref", "alias")]
    return Ref(menu)


class UnknownRef(_RustRef):
    def __init__(self, tree_index, datum, tree_config):
        super(UnknownRef, self).__init__(tree_index, None, tree_config)
        if datum['refid'] and datum['refid'] in tree_index.data.unknowns:
            unknown = tree_index.data.unknowns[datum['refid']]
            urls = None
            if unknown['crate'] in tree_index.locations:
                urls = tree_index.locations[unknown['crate']]
            self.menu_data = [trim_dict(datum, ['refid']), urls]
        else:
            warn("unknown unknown!")

    def menu_items(self):
        if self.menu_data:
            datum, urls = self.menu_data
            menu = [find_references_menu(self.tree, str(datum['refid']), "extern-ref", "item")]
            if urls:
                menu.extend(std_lib_links(urls))
            return menu
