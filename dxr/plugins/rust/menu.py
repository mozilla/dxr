import os

from dxr.lines import Ref
from dxr.menus import MenuMaker, MultiDatumMenuMaker, SingleDatumMenuMaker
from dxr.utils import search_url


def quote(qualname):
    """ Wrap qualname in quotes if it contains spaces """
    if ' ' in qualname:
        qualname = '"' + qualname + '"'
    return qualname


def truncate_value(value, typ=""):
    result = ""
    if value:
        eol = value.find('\n')
        if eol < 0:
            result = value.strip()
        else:
            value = value[0:eol]
            value = value.strip()
            result = value + " ..."

    if typ:
        if result:
            result = typ + ": " + result
        else:
            result = typ

    if not result:
        return None

    return result


class _RustPluginAttr(object):
    plugin = 'rust'


class FindReferencesMenuMaker(SingleDatumMenuMaker, _RustPluginAttr):
    """A sort of compound menumaker that handles finding various sorts of
    references

    Should be broken into several.

    """
    def menu_items(self):
        kind, filter, qualname = self.data
        yield {'html':   "Find references",
               'title':  "Find references to this " + kind,
               'href':   search_url(self.tree, "+" + filter + ":%s" % quote(qualname)),
               'icon':   'reference'}


def add_find_references(tree_config, menu, qualname, filter, kind):
    menu.append(FindReferencesMenuMaker(tree_config, (kind, filter, qualname)))


class StdLibMenuMaker(SingleDatumMenuMaker, _RustPluginAttr):
    def menu_items(self):
        # TODO: Stop storing entire URLs in ES.
        def get_domain(url):
            start = url.find('//') + 2
            return url[start:url.find('/', start)]

        def add_link_to_menu(url, html, title):
            if url:
                menu.append({'html': html,
                             'title': title,
                             'href': url,
                             'icon': 'jump'})

        menu = []
        doc_url, src_url, dxr_url, extra_text = self.data
        add_link_to_menu(doc_url,
                         'Go to docs' + extra_text,
                         'Go to documentation for this crate on ' + get_domain(doc_url))
        add_link_to_menu(src_url,
                         'Go to source' + extra_text,
                         'Go to source code for this crate on ' + get_domain(doc_url))
        add_link_to_menu(dxr_url,
                         'Go to DXR index' + extra_text,
                         'Go to DXR index of this crate on ' + get_domain(doc_url))
        return menu


def std_lib_links(tree_config, menu, (docurl, srcurl, dxrurl), extra_text = ""):
    menu.insert(0, StdLibMenuMaker(tree_config, (doc_url, src_url, dxr_url, extra_text)))


def function_menu_generic(datum, tree_config):
    """Return menu makers shared by function def/decls and function refs."""
    makers = [CallMenuMaker(tree_config, datum)]
    add_find_references(tree_config, makers, datum['qualname'], "function-ref", "function")
    return makers


class _RustPluginAttr(object):
    plugin = 'rust'


class CallMenuMaker(SingleDatumMenuMaker, _RustPluginAttr):
    def menu_items(self):
        qualname = self.data
        return [{'html': "Find callers",
                 'title': "Find functions that call this function",
                 'href': search_url(self.tree, "+callers:%s" % quote(qualname)),
                 'icon': 'method'},
                {'html': "Find callees",  # TODO: Probably useless. Remove.
                 'title': "Find functions that are called by this function",
                 'href': search_url(self.tree, "+called-by:%s" % quote(qualname)),
                 'icon': 'method'}]


# TODO: DRY with clang plugin.
class _JumpToTarget(MultiDatumMenuMaker):
    """A MenuMaker that jumps straight to a specific line of a file

    :classvar target_name: A description of the kind of thing I point to, like
        "trait method" or "function definition"

    """
    def __init__(self, tree, path, row):
        super(_JumpToTarget, self).__init__(tree)
        self.path = path
        self.row = row

    def es(self):
        return self.path, self.row

    @classmethod
    def from_decl(cls, tree, decl):
        """Return an instance made from a declaration mapping.

        If the incoming declaration doesn't warrant the creation of a menu,
        return None.

        """
        path = decl['file_name']
        if path:
            return cls(tree, path, decl['file_line'])
        else:
            warn("Can't add jump to empty path.")  # Can this happen?

    def menu_items(self):
        yield {'html': 'Jump to %s' % self.target_name,
               'title': "Jump to %s in '%s'" % (self.target_name,
                                                os.path.basename(self.path)),
               'href': url_for(BROWSE, tree=self.tree.name, path=self.path, _anchor=self.row),
               'icon': 'jump'}


class JumpToTraitMethodMenuMaker(_JumpToTarget, _RustPluginAttr):
    target_name = 'trait method'


class JumpToDefinitionMenuMaker(_JumpToTarget, _RustPluginAttr):
    target_name = 'definition'


class JumpToModuleDefinitionMenuMaker(_JumpToTarget, _RustPluginAttr):
    target_name = 'module defintion'


class JumpToModuleDeclarationMenuMaker(_JumpToTarget, _RustPluginAttr):
    target_name = 'module declaration'


class JumpToAliasDefinitionMenuMaker(_JumpToTarget, _RustPluginAttr):
    target_name = 'alias defintion'


class JumpToCrateMenuMaker(_JumpToTarget, _RustPluginAttr):
    target_name = 'crate'


class JumpToTypeDeclarationMenuMaker(_JumpToTarget, _RustPluginAttr):
    target_name = 'type declaration'


class JumpToVariableDeclarationMenuMaker(_JumpToTarget, _RustPluginAttr):
    target_name = 'variable declaration'


class JumpToFunctionDeclarationMenuMaker(_JumpToTarget, _RustPluginAttr):
    target_name = 'function declaration'


class TraitImplMenuMaker(SingleDatumMenuMaker):
    def menu_items(self):
        qualname, count = self.data
        yield {'html': "Find implementations (%d)" % self.count,
               'title': "Find implementations of this trait method",
               'href': search_url(self.tree, "+fn-impls:%s" % quote(self.qualname)),
               'icon': 'method'}


def function_menu(tree, datum, tree_config):
    makers = []
    if 'declid' in datum and datum['declid'] in tree.data.functions:
        # It's an implementation; find the decl:
        decl = tree.data.functions[datum['declid']]
        makers.append(JumpToTraitMethodMenuMaker.from_decl(tree_config, decl))
    else:
        # it's a decl, find implementations
        impls = tree.data.index('functions', 'declid')
        count = len(impls[datum['id']]) if datum['id'] in impls else 0
        if count:
            makers.append(TraitImplMenuMaker(tree_config, (datum['qualname'], count)))
    makers = [CallMenuMaker(tree_config, datum['qualname'])]

    return Ref(makers)  # TODO: Filter out Nones in makers, here and elsewhere? Do they actually happen?


def function_ref_menu(tree, datum, tree_config):
    """Return a Ref with menus suitable to a function reference."""
    fn_def = None
    fn_decl = None
    if 'refid' in datum and datum['refid'] and datum['refid'] in tree.data.functions:
        fn_def = tree.data.functions[datum['refid']]
    elif 'refid' in datum and datum['refid'] and datum['refid'] in tree.data.types:
        # enum variant ctors
        fn_def = tree.data.types[datum['refid']]
    if 'declid' in datum and datum['declid'] and datum['declid'] in tree.data.functions:
        fn_decl = tree.data.functions[datum['declid']]

    makers = []
    name = None
    if fn_def:
        makers.append(JumpToDefinitionMenuMaker.from_decl(tree_config, fn_def))
        if fn_decl and (fn_def['file_name'] != fn_decl['file_name'] or fn_def['file_line'] != fn_decl['file_line']):
            makers.append(JumpToTraitMethodMenuMaker.from_decl(tree_config, fn_decl))
        makers.extend(function_menu_generic(fn_def, tree_config))
        name = fn_def['qualname']
    elif fn_decl:
        makers = function_menu_generic(fn_decl, tree_config)
        makers.append(JumpToTraitMethodMenuMaker.from_decl(tree_config, fn_decl))
        name = fn_decl['qualname']

    # FIXME(#12) should have type, not name for title
    return Ref(makers, hover=name)


def variable_menu_generic(tree, datum, tree_config):
    menu = []
    add_find_references(tree_config, menu, datum['qualname'], "var-ref", "variable")
    return menu


def variable_menu(tree, datum, tree_config):
    menu = variable_menu_generic(tree, datum, tree_config)
    typ = None
    if 'type' in datum:
        typ = datum['type']
    else:
        warn("no type for variable %s" % (datum['qualname'],))
    return Ref(menu, hover=truncate_value("", typ))


def variable_ref_menu(tree, datum, tree_config):
    if datum['refid'] and datum['refid'] in tree.data.variables:
        makers = []
        var = tree.data.variables[datum['refid']]
        makers.append(JumpToDefinitionMenuMaker.from_decl(tree_config, var))
        makers.extend(variable_menu_generic(tree, var, tree_config))
        typ = None
        if 'type' in var:
            typ = var['type']
        else:
            warn("no type for variable ref %s" % (var['qualname'],))
        return Ref(makers, hover=truncate_value(typ, var['value']))

    # TODO what is the culprit here?
    #print "variable ref missing def"


class TypeMenuMaker(SingleDatumMenuMaker, _RustPluginAttr):
    def menu_items(self):
        kind, qualname = self.data
        if kind == 'trait':
            yield {'html': "Find sub-traits",
                   'title': "Find sub-traits of this trait",
                   'href': search_url(tree_config, "+derived:%s" % quote(qualname)),
                   'icon': 'type'}
            yield {'html': "Find super-traits",
                   'title': "Find super-traits of this trait",
                   'href': search_url(tree_config, "+bases:%s" % quote(qualname)),
                   'icon': 'type'}
        if kind == 'struct' or kind == 'enum' or kind == 'trait':
            yield {'html': "Find impls",
                   'title': "Find impls which involve this " + kind,
                   'href': search_url(tree_config, "+impl:%s" % quote(qualname)),
                   'icon': 'reference'}


def type_menu_generic(tree, datum, tree_config):
    kind = datum['kind']
    qualname = datum['qualname']
    menu = [TypeMenuMaker(tree_config, (kind, qualname))]
    add_find_references(tree_config, menu, qualname, "type-ref", kind)
    return menu


def type_menu(tree, datum, tree_config):
    return Ref(type_menu_generic(tree, datum, tree_config))


def type_ref_menu(tree, datum, tree_config):
    if datum['refid'] and datum['refid'] in tree.data.types:
        typ = tree.data.types[datum['refid']]
        makers = [JumpToDefinitionMenuMaker.from_decl(tree_config, typ)]
        makers.extend(type_menu_generic(tree, typ, tree_config))
        title = None
        if 'value' in typ:
            title = typ['value']
        else:
            warn('no value for %s %s' % (typ['kind'], typ['qualname']))
        return Ref(makers, hover=truncate_value("", title))


class UseItemsMenuMaker(SingleDatumMenuMaker, _RustPluginAttr):
    def menu_items(self):
        qualname = self.data
        yield {'html': "Find use items",
               'title': "Find instances of this module in 'use' items",
               'href': search_url(self.tree, "+module-use:%s" % quote(qualname)),
               'icon': 'reference'}


def module_menu_generic(tree, datum, tree_config):
    menu = [UseItemsMenuMaker(tree_config, datum['qualname'])]
    add_find_references(tree_config, menu, datum['qualname'], "module-ref", "module")
    return menu


def module_menu(tree, datum, tree_config):
    makers = []
    if datum['def_file'] != datum['file_name']:
        makers.append(JumpToModuleDefinitionMenuMaker(tree_config,
                                                      datum['def_file'],
                                                      1))
    makers.extend(module_menu_generic(tree, datum, tree_config))
    return Ref(makers)


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
                    makers.append(JumpToAliasDefinitionMenuMaker.from_decl(tree_config, mod))
                if 'location' in alias and alias['location'] in tree.crates_by_name:
                    # Add references to extern mods via aliases (known local crates)
                    crate = tree.crates_by_name[alias['location']]
                    makers.append(JumpToCrateMenuMaker(tree_config, crate['file_name'], 1))
                    add_find_references(tree_config, makers, alias['qualname'], "module-alias-ref", "alias")
                elif 'location' in alias and alias['location'] in tree.locations:
                    # Add references to extern mods via aliases (standard library crates)
                    urls = tree.locations[alias['location']]
                    makers = []
                    add_find_references(tree_config, makers, alias['qualname'], "module-alias-ref", "alias")
                    std_lib_links(tree_config, makers, urls)
                elif 'location' in alias:
                    # Add references to extern mods via aliases (unknown local crates)
                    makers = []
                    add_find_references(tree_config, makers, alias['qualname'], "module-alias-ref", "alias")
                elif 'file_name' in mod:
                    makers.append(JumpToModuleDefinitionMenuMaker.from_decl(tree_config, mod))
            else:
                if 'file_name' in mod and 'def_file' in mod and mod['def_file'] == mod['file_name']:
                    makers.append(JumpToDefinitionMenuMaker.from_decl(tree_config, mod))
                else:
                    makers.append(JumpToModuleDefinitionMenuMaker(tree_config, mod['def_file'], 1))
                    makers.append(JumpToModuleDeclarationMenuMaker.from_decl(tree_config, mod))
            makers.extend(module_menu_generic(tree, mod, tree_config))
            return Ref(makers)

        # types masquerading as modules
        if datum['refid'] in tree.data.types:
            typ = tree.data.types[datum['refid']]
            makers = [JumpToDefinitionMenuMaker.from_decl(tree_config, typ)]
            makers.extend(type_menu_generic(tree, typ, tree_config))
            title = None
            if 'value' in typ:
                title = typ['value']
            else:
                warn('no value for %s %s' % (typ['kind'], typ['qualname']))
            return Ref(makers, hover=truncate_value('', title))


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
            makers = [JumpToModuleDefinitionMenuMaker(tree_config, mod['def_file'], 1)]
            add_find_references(tree_config, makers, datum['qualname'], "module-alias-ref", "alias")
            return Ref(makers)

    # 'module' aliases to types
    if datum['refid'] and datum['refid'] in tree.data.types:
        typ = tree.data.types[datum['refid']]
        if typ['name'] != datum['name']:
            makers = [JumpToTypeDeclarationMenuMaker.from_decl(tree_config, typ)]
            add_find_references(tree_config, makers, datum['qualname'], "type-ref", "alias")
            return Ref(makers)

    # 'module' aliases to variables
    if datum['refid'] and datum['refid'] in tree.data.variables:
        var = tree.data.variables[datum['refid']]
        if var['name'] != datum['name']:
            makers = [JumpToVariableDeclarationMenuMaker.from_decl(tree_config, var)]
            add_find_references(tree_config, makers, datum['qualname'], "var-ref", "alias")
            return Ref(makers)

    # 'module' aliases to functions
    if datum['refid'] and datum['refid'] in tree.data.functions:
        fn = tree.data.functions[datum['refid']]
        if fn['name'] != datum['name']:
            makers = [JumpToFunctionDeclarationMenuMaker.from_decl(tree_config, fn)]
            add_find_references(tree_config, makers, datum['qualname'], "function-ref", "alias")
            return Ref(makers)

    # extern crates to known local crates
    if 'location' in datum and datum['location'] and datum['location'] in tree.crates_by_name:
        crate = tree.crates_by_name[datum['location']]
        makers = [JumpToCrateMenuMaker(tree_config, crate['file_name'], 1)]
        add_find_references(tree_config, makers, datum['qualname'], "module-alias-ref", "alias")
        return Ref(makers)

    # extern crates to standard library crates
    if 'location' in datum and datum['location'] and datum['location'] in tree.locations:
        urls = tree.locations[datum['location']]
        menu = []
        add_find_references(tree_config, menu, datum['qualname'], "module-alias-ref", "alias")
        std_lib_links(tree_config, menu, urls)
        return Ref(menu)

    # other references to standard library items
    if datum['refid'] in tree.data.unknowns:
        # FIXME We could probably do better and link to the precise type or static in docs etc., rather than just the crate
        urls = tree.locations[tree.data.unknowns[datum['refid']]['crate']]
        menu = []
        add_find_references(tree_config, menu, datum['qualname'], "module-alias-ref", "alias")
        std_lib_links(tree_config, menu, urls)
        return Ref(menu)

    # extern mods to unknown local crates
    menu = []
    add_find_references(tree_config, menu, datum['qualname'], "module-alias-ref", "alias")
    return Ref(menu)


def unknown_ref_menu(tree, datum, tree_config):
    if datum['refid'] and datum['refid'] in tree.data.unknowns:
        unknown = tree.data.unknowns[datum['refid']]
        menu = []
        add_find_references(tree_config, menu, str(datum['refid']), "extern-ref", "item")
        if unknown['crate'] in tree.locations:
            urls = tree.locations[unknown['crate']]
            std_lib_links(tree_config, menu, urls)
        return Ref(menu)

    warn("unknown unknown!")
