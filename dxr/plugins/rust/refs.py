from warnings import warn

from dxr.lines import Ref
# import ALL THE THINGS
from dxr.plugins.rust.menu import (
    jump_to_target_from_decl, jump_to_definition_menu,
    jump_to_trait_method_menu, function_menu_generic, variable_menu_generic, truncate_value,
    type_menu_generic, jump_to_module_definition_menu, module_menu_generic,
    jump_to_alias_definition_menu, jump_to_crate_menu, find_references_menu, std_lib_links,
    jump_to_module_declaration_menu, jump_to_type_declaration_menu, trait_impl_menu)


def trim_dict(dictionary, keys):
    """Return a new dict with given keys set from dictionary arg.

    A key listed in keys but not in the dictionary will not be set in the returned dict.
    """

    if dictionary:
        return dict((key, dictionary[key]) for key in keys if key in dictionary)


class _RustRef(Ref):
    plugin = 'rust'

    def __init__(self, tree_config, menu_data, tree_index=None, hover=None, qualname=None, qualname_hash=None):
        super(_RustRef, self).__init__(tree_config, None, hover, qualname, qualname_hash)
        if tree_index:
            # If we are at index time, then prepare menu_data for ES insertion.
            # Otherwise we know we already have menu_data populated from previous preparation.
            self.menu_data = self.prepare_menu_data(tree_index, menu_data)
        else:
            self.menu_data = menu_data

    def prepare_menu_data(self, tree_index, datum):
        raise NotImplementedError


class _KeysFromDatum(_RustRef):
    """A Ref superclass that only holds onto certain keys of a datum dict.

    :classvar keys: a list of dict keys which will be kept in the data to pass to ES.
    """

    def __init__(self, tree_config, datum, tree_index=None, hover=None, qualname=None, qualname_hash=None):
        super(_KeysFromDatum, self).__init__(tree_config, datum, tree_index, hover, qualname, qualname_hash)

    def prepare_menu_data(self, tree_index, datum):
        return trim_dict(datum, self.keys)


class FunctionRef(_RustRef):
    def prepare_menu_data(self, tree_index, datum):
        if 'declid' in datum and datum['declid'] in tree_index.data.functions:
            # It's an implementation; find the decl:
            decl = tree_index.data.functions[datum['declid']]
            return [trim_dict(datum, ['qualname']), trim_dict(decl, ['file_name', 'file_line']), 0]
        else:
            # It's a decl; find implementations:
            impls = tree_index.data.index('functions', 'declid')
            count = len(impls[datum['id']]) if datum['id'] in impls else 0
            return [trim_dict(datum, ['qualname']), None, count]

    def menu_items(self):
        # decl is only defined if datum is not a decl (i.e. we're looking at an impl).
        datum, decl, count = self.menu_data
        menus = function_menu_generic(datum, self.tree)
        if decl:
            menus.insert(0, jump_to_target_from_decl(jump_to_trait_method_menu, self.tree, decl))
        elif count:
            menus.append(trait_impl_menu(self.tree, datum['qualname'], count))
        return menus


class FunctionRefRef(_RustRef):
    """A Ref with menus suitable to a function reference."""

    def prepare_menu_data(self, tree_index, datum):
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
        return [trim_dict(fn_def, data_keys), trim_dict(fn_decl, data_keys)]

    def menu_items(self):
        fn_def, fn_decl = self.menu_data
        menus = []
        if fn_def:
            menus.insert(0, jump_to_target_from_decl(jump_to_definition_menu, self.tree, fn_def))
            if fn_decl and (fn_def['file_name'] != fn_decl['file_name'] or fn_def['file_line'] != fn_decl['file_line']):
                menus.insert(0, jump_to_target_from_decl(jump_to_trait_method_menu, self.tree, fn_decl))
            menus.extend(function_menu_generic(fn_def, self.tree))
        elif fn_decl:
            menus = function_menu_generic(fn_decl, self.tree)
            menus.insert(0, jump_to_target_from_decl(jump_to_trait_method_menu, self.tree, fn_decl))
        return menus


class VariableRef(_KeysFromDatum):
    keys = ['type', 'qualname']

    def __init__(self, tree_config, datum, tree_index=None, hover=None, qualname=None, qualname_hash=None):
        super(VariableRef, self).__init__(tree_config, datum, tree_index,
                                          truncate_value("", datum.get('type')), qualname,
                                          qualname_hash)

    def menu_items(self):
        menu = variable_menu_generic(self.menu_data, self.tree)
        typ = self.menu_data.get('type')
        if not typ:
            qualname = self.menu_data.get('qualname')
            warn("no type for variable %s, so the tooltip will be missing" % qualname)
        return menu


class VariableRefRef(_RustRef):
    def prepare_menu_data(self, tree_index, datum):
        if datum['refid'] and datum['refid'] in tree_index.data.variables:
            var = tree_index.data.variables[datum['refid']]
            typ = None
            if 'type' in var:
                typ = var['type']
            else:
                warn("no type for variable ref %s" % (var['qualname'],))
            self.hover = truncate_value(typ, var['value'])
            return trim_dict(datum, ['file_line', 'file_name', 'qualname'])
        # TODO what is the culprit here?
        # print "variable ref missing def"

    def menu_items(self):
        if self.menu_data:
            menus = [jump_to_target_from_decl(jump_to_definition_menu, self.tree, self.menu_data)]
            menus.extend(variable_menu_generic(self.menu_data, self.tree))
            return menus
        return []


class TypeRef(_KeysFromDatum):
    keys = ['kind', 'qualname']

    def menu_items(self):
        return type_menu_generic(self.menu_data, self.tree)


class TypeRefRef(_RustRef):
    def prepare_menu_data(self, tree_index, datum):
        if datum['refid'] and datum['refid'] in tree_index.data.types and 'kind' in datum:
            typ = tree_index.data.types[datum['refid']]
            title = None
            if 'value' in typ:
                title = typ['value']
            else:
                warn('no value for %s %s' % (typ['kind'], typ['qualname']))
            self.hover = truncate_value("", title)
            return trim_dict(datum, ['file_line', 'file_name', 'qualname', 'kind'])

    def menu_items(self):
        if self.menu_data:
            return ([jump_to_target_from_decl(jump_to_definition_menu, self.tree, self.menu_data)]
                    + type_menu_generic(self.menu_data, self.tree))
        return []


class ModuleRef(_KeysFromDatum):
    keys = ['def_file', 'file_name', 'file_line']

    def menu_items(self):
        if self.menu_data['def_file'] != self.menu_data['file_name']:
            yield jump_to_module_definition_menu(self.tree, self.menu_data['def_file'], 1)


class ModuleRefRef(_RustRef):
    def prepare_menu_data(self, tree_index, datum):

        mod, alias, crate, urls, typ = [None]*5
        if datum['refid']:
            # Mod can be in either local crate or extern crate.
            mod = (tree_index.data.modules.get(datum['refid'])
                   or tree_index.data.extern_crate_mods.get(datum['refid']))
            if mod:
                if datum['aliasid'] and datum['aliasid'] in tree_index.data.module_aliases:
                    alias = tree_index.data.module_aliases[datum['aliasid']]
                    if 'location' in alias:
                        if alias['location'] in tree_index.crates_by_name:
                            crate = tree_index.crates_by_name[alias['location']]
                        elif alias['location'] in tree_index.locations:
                            urls = tree_index.locations[alias['location']]

        # types masquerading as modules
        if datum['refid'] in tree_index.data.types:
            typ = tree_index.data.types[datum['refid']]
            if 'value' in typ:
                self.hover = typ['value']
            else:
                warn('no value for %s %s' % (typ['kind'], typ['qualname']))

        return datum, mod, alias, crate, urls, typ

    def menu_items(self):
        # self.menu_data comes in the way of [datum, mod, alias, secondary_datum, type_datum],
        # where (mod, alias, secondary_datum) and type_datum are mutually exclusive.

        datum, mod, alias, crate, urls, typ = self.menu_data
        menus = []
        if mod:
            if 'file_name' in mod:
                menus.append(jump_to_target_from_decl(jump_to_alias_definition_menu, self.tree, mod))
            if crate:
                # Add references to extern mods via aliases (known local crates)
                menus.append(jump_to_crate_menu(self.tree, crate['file_name'], 1))
                menus.append(find_references_menu(self.tree, alias['qualname'], "module-alias-ref", "alias"))
            if urls:
                # Add references to extern mods via aliases (standard library crates)
                menus = [find_references_menu(self.tree, alias['qualname'], "module-alias-ref", "alias")]
                menus.extend(std_lib_links(urls))
            elif alias and 'location' in alias:
                # Add references to extern mods via aliases (unknown local crates)
                menus = [find_references_menu(self.tree, alias['qualname'], "module-alias-ref", "alias")]
            elif 'file_name' in mod:
                menus.insert(0, jump_to_target_from_decl(jump_to_module_definition_menu, self.tree, mod))
            else:
                if 'file_name' in mod and 'def_file' in mod and mod['def_file'] == mod['file_name']:
                    menus.insert(0, jump_to_target_from_decl(jump_to_definition_menu, self.tree, mod))
                else:
                    menus.insert(0, jump_to_target_from_decl(jump_to_module_declaration_menu, self.tree, mod))
                    menus.insert(0, jump_to_module_definition_menu(self.tree, mod['def_file'], 1))
            menus.extend(module_menu_generic(mod, self.tree))
        elif typ:
            menus = [jump_to_target_from_decl(jump_to_definition_menu, self.tree, typ)]
            menus.extend(type_menu_generic(typ, self.tree))
        return menus


class ModuleAliasRef(_RustRef):
    def prepare_menu_data(self, tree_index, datum):

        datum_keys = ['qualname']
        secondary_keys = ['file_name', 'file_line', 'def_file']

        # menu_data will be [datum, kind, aliased_datum], where kind is of
        # {'modules', 'types', 'variables', 'functions', 'crate','urls'}, describing the target.
        kind, aliased_datum = None, None

        # 'module' aliases to modules, types, variables, and functions
        for table_name in ['modules', 'types', 'variables', 'functions']:
            # Pull out each instance var from the tree's index data table and see if it contains
            #  this refid.
            index_table = getattr(tree_index.data, table_name)
            if datum['refid'] and datum['refid'] in index_table:
                secondary_datum = index_table[datum['refid']]
                if secondary_datum['name'] != datum['name']:
                    kind, aliased_datum = index_table, trim_dict(secondary_datum, secondary_keys)

        # extern crates to known local crates
        if 'location' in datum and datum['location'] and datum['location'] in tree_index.crates_by_name:
            kind, aliased_datum = 'crate', trim_dict(tree_index.crates_by_name[datum['location']], secondary_keys)

        # extern crates to standard library crates
        if 'location' in datum and datum['location'] and datum['location'] in tree_index.locations:
            kind, aliased_datum = 'urls', tree_index.locations[datum['location']]

        # other references to standard library items
        if datum['refid'] in tree_index.data.unknowns:
            # FIXME We could probably do better and link to the precise type or static in docs etc., rather than just the crate
            kind, aliased_datum = 'urls', tree_index.locations[tree_index.data.unknowns[datum['refid']]['crate']]

        return trim_dict(datum, datum_keys), kind, aliased_datum

    def menu_items(self):
        datum, kind, aliased_datum = self.menu_data
        if not kind:
            return [find_references_menu(self.tree, datum['qualname'], "module-alias-ref", "alias")]
        elif kind == 'modules':
            return [jump_to_module_definition_menu(self.tree, aliased_datum['def_file'], 1),
                    find_references_menu(aliased_datum, datum['qualname'], "module-alias-ref", "alias")]
        elif kind == 'types':
            return [jump_to_target_from_decl(jump_to_type_declaration_menu, self.tree, aliased_datum),
                    find_references_menu(self.tree, datum['qualname'], "type-ref", "alias")]
        elif kind == 'variables':
            return [jump_to_target_from_decl(jump_to_type_declaration_menu, self.tree, aliased_datum),
                    find_references_menu(self.tree, datum['qualname'], "var-ref", "alias")]
        elif kind == 'functions':
            return [jump_to_target_from_decl(jump_to_type_declaration_menu, self.tree, aliased_datum),
                    find_references_menu(self.tree, datum['qualname'], "function-ref", "alias")]
        elif kind == 'crate':
            return [jump_to_crate_menu(self.tree, aliased_datum['file_name'], 1),
                    find_references_menu(self.tree, datum['qualname'], "module-alias-ref", "alias")]
        elif kind == 'urls':
            return std_lib_links(aliased_datum)
        return []


class UnknownRef(_RustRef):
    def prepare_menu_data(self, tree_index, datum):
        if datum['refid'] and datum['refid'] in tree_index.data.unknowns:
            unknown = tree_index.data.unknowns[datum['refid']]
            urls = None
            if unknown['crate'] in tree_index.locations:
                urls = tree_index.locations[unknown['crate']]
            return [trim_dict(datum, ['refid']), urls]
        else:
            warn("unknown unknown!")

    def menu_items(self):
        if self.menu_data:
            datum, urls = self.menu_data
            menu = [find_references_menu(self.tree, str(datum['refid']), "extern-ref", "item")]
            if urls:
                menu.extend(std_lib_links(urls))
            return menu
