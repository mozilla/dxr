import os
from dxr.utils import search_url

def search(tree_config, query):
    """ Auxiliary function for getting the search url for query """
    return search_url(tree_config.config.www_root,
                      tree_config.name,
                      query)

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


def add_jump_definition(tree, tree_config, menu, datum, text="Jump to definition"):
    """ Add a jump to definition to the menu """
    add_jump_definition_to_line(tree, tree_config, menu, datum['file_name'], datum['file_line'], text="Jump to definition")

def add_jump_definition_to_line(tree, tree_config, menu, path, line, text="Jump to definition"):

    if not path:
        print "Can't add jump to empty path. Menu:", menu
        print "text: ", text
        return

    # Definition url
    url = tree_config.config.www_root + '/' + tree_config.name + '/source/' + path
    url += "#%s" % line
    menu.insert(0, { 
        'html':   text,
        'title':  "%s in '%s'" % (text, os.path.basename(path)),
        'href':   url,
        'icon':   'jump'
    })

def add_find_references(tree_config, menu, qualname, search_term, kind):
    menu.append({
        'html':   "Find references",
        'title':  "Find references to this " + kind,
        'href':   search(tree_config, "+" + search_term + ":%s" % quote(qualname)),
        'icon':   'reference'
    })


def std_lib_links(tree_config, menu, (docurl, srcurl, dxrurl), extra_text = ""):
    def get_domain(url):
        start = url.find('//') + 2
        return url[start:url.find('/', start)]

    def add_link_to_menu(menu, url, text, long_text):
        if not url:
            return menu;

        menu.insert(0, {
            'html':   text,
            'title':  long_text,
            'href':   url,
            'icon':   'jump'
        })
        return menu

    add_link_to_menu(menu, dxrurl,
                     "Go to DXR index" + extra_text,
                     "Go to DXR index of this crate on " + get_domain(dxrurl))
    add_link_to_menu(menu, srcurl,
                     "Go to source" + extra_text,
                     "Go to source code for this crate on " + get_domain(srcurl))
    add_link_to_menu(menu, docurl,
                     "Go to docs" + extra_text,
                     "Go to documentation for this crate on " + get_domain(docurl))


# Menu items shared by function def/decls and function refs
def function_menu_generic(tree, datum, tree_config):
    menu = []
    menu.append({
        'html':   "Find callers",
        'title':  "Find functions that call this function",
        'href':   search(tree_config, "+callers:%s" % quote(datum['qualname'])),
        'icon':   'method'
    })
    menu.append({
        'html':   "Find callees",
        'title':  "Find functions that are called by this function",
        'href':   search(tree_config, "+called-by:%s" % quote(datum['qualname'])),
        'icon':   'method'
    })
    add_find_references(tree_config, menu, datum['qualname'], "function-ref", "function")
    return menu


def function_menu(tree, datum, tree_config):
    menu = function_menu_generic(tree, datum, tree_config)

    if 'declid' in datum and datum['declid'] in tree.data.functions:
        # it's an implementation, find the decl
        decl = tree.data.functions[datum['declid']]
        add_jump_definition(tree, tree_config, menu, decl, "Jump to trait method")
    else:
        # it's a decl, find implementations
        impls = tree.data.index('functions', 'declid')
        count = len(impls[datum['id']]) if datum['id'] in impls else 0
        if count > 0:
            menu.append({
                'html':   "Find implementations (%d)"%count,
                'title':  "Find implementations of this trait method",
                'href':   search(tree_config, "+fn-impls:%s" % quote(datum['qualname'])),
                'icon':   'method'
            })

    return (menu, None)


def function_ref_menu(tree, datum, tree_config):
    fn_def = None
    fn_decl = None
    if 'refid' in datum and datum['refid'] and datum['refid'] in tree.data.functions:
        fn_def = tree.data.functions[datum['refid']]
    elif 'refid' in datum and datum['refid'] and datum['refid'] in tree.data.types:
        # enum variant ctors
        fn_def = tree.data.types[datum['refid']]
    if 'declid' in datum and datum['declid'] and datum['declid'] in tree.data.functions:
        fn_decl = tree.data.functions[datum['declid']]

    menu = []
    name = None
    if fn_def:
        menu = function_menu_generic(tree, fn_def, tree_config)
        if fn_decl and (fn_def['file_name'] != fn_decl['file_name'] or fn_def['file_line'] != fn_decl['file_line']):
            add_jump_definition(tree, tree_config, menu, fn_decl, "Jump to trait method")
        add_jump_definition(tree, tree_config, menu, fn_def)
        name = fn_def['qualname']
    elif fn_decl:
        menu = function_menu_generic(tree, fn_decl, tree_config)
        add_jump_definition(tree, tree_config, menu, fn_decl, "Jump to trait method")
        name = fn_decl['qualname']

    # FIXME(#12) should have type, not name for title
    return (menu, name)


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
        print "no type for variable", datum['qualname']
    return (menu, truncate_value("", typ))


def variable_ref_menu(tree, datum, tree_config):
    if datum['refid'] and datum['refid'] in tree.data.variables:
        var = tree.data.variables[datum['refid']]
        menu = variable_menu_generic(tree, var, tree_config)
        add_jump_definition(tree, tree_config, menu, var)
        typ = None
        if 'type' in var:
            typ = var['type']
        else:
            print "no type for variable ref", var['qualname']
        return (menu, truncate_value(typ, var['value']))

    # TODO what is the culprit here?
    #print "variable ref missing def"
    return None


def type_menu_generic(tree, datum, tree_config):
    menu = []
    kind = datum['kind']
    if kind == 'trait':
        menu.append({
            'html':   "Find sub-traits",
            'title':  "Find sub-traits of this trait",
            'href':   search(tree_config, "+derived:%s" % quote(datum['qualname'])),
            'icon':   'type'
        })
        menu.append({
            'html':   "Find super-traits",
            'title':  "Find super-traits of this trait",
            'href':   search(tree_config, "+bases:%s" % quote(datum['qualname'])),
            'icon':   'type'
        })
    
    if kind == 'struct' or kind == 'enum' or kind == 'trait':
        menu.append({
            'html':   "Find impls",
            'title':  "Find impls which involve this " + kind,
            'href':   search(tree_config, "+impl:%s" % quote(datum['qualname'])),
            'icon':   'reference'
        })
    add_find_references(tree_config, menu, datum['qualname'], "type-ref", kind)
    return menu

def type_menu(tree, datum, tree_config):
    return (type_menu_generic(tree, datum, tree_config), None)

def type_ref_menu(tree, datum, tree_config):
    if datum['refid'] and datum['refid'] in tree.data.types:
        typ = tree.data.types[datum['refid']]
        menu = type_menu_generic(tree, typ, tree_config)
        add_jump_definition(tree, tree_config, menu, typ)
        title = None
        if 'value' in typ:
            title = typ['value']
        else:
            print "no value for", typ['kind'], typ['qualname']
        return (menu, truncate_value("", title))

    return None


def module_menu_generic(tree, datum, tree_config):
    menu = []
    menu.append({
        'html':   "Find use items",
        'title':  "Find instances of this module in 'use' items",
        'href':   search(tree_config, "+module-use:%s" % quote(datum['qualname'])),
        'icon':   'reference'
    })
    add_find_references(tree_config, menu, datum['qualname'], "module-ref", "module")
    return menu

def module_menu(tree, datum, tree_config):
    menu = module_menu_generic(tree, datum, tree_config)
    if datum['def_file'] != datum['file_name']:
        add_jump_definition_to_line(tree, tree_config, menu, datum['def_file'], 1, "Jump to module defintion")
    return (menu, None)


def module_ref_menu(tree, datum, tree_config):
    # Add straightforward aliases to modules
    if datum['refid']:
        mod = None
        if datum['refid'] in tree.data.modules:
            mod = tree.data.modules[datum['refid']]
        elif datum['refid'] in tree.data.extern_crate_mods:
            mod = tree.data.extern_crate_mods[datum['refid']]

        if mod:
            menu = module_menu_generic(tree, mod, tree_config)
            if datum['aliasid'] and datum['aliasid'] in tree.data.module_aliases:
                alias = tree.data.module_aliases[datum['aliasid']]
                if 'location' in alias and alias['location'] in tree.crates_by_name:
                    # Add references to extern mods via aliases (known local crates)
                    crate = tree.crates_by_name[alias['location']]
                    menu = []
                    add_find_references(tree_config, menu, alias['qualname'], "module-alias-ref", "alias")
                    add_jump_definition_to_line(tree, tree_config, menu, crate['file_name'], 1, "Jump to crate")
                elif 'location' in alias and alias['location'] in tree.locations:
                    # Add references to extern mods via aliases (standard library crates)
                    urls = tree.locations[alias['location']]
                    menu = []
                    add_find_references(tree_config, menu, alias['qualname'], "module-alias-ref", "alias")
                    std_lib_links(tree_config, menu, urls)
                elif 'location' in alias:
                    # Add references to extern mods via aliases (unknown local crates)
                    menu = []
                    add_find_references(tree_config, menu, alias['qualname'], "module-alias-ref", "alias")
                elif 'file_name' in mod:
                    add_jump_definition(tree, tree_config, menu, mod, "Jump to module defintion")
                if 'file_name' in mod:
                    add_jump_definition(tree, tree_config, menu, mod, "Jump to alias defintion")
            else:
                if 'file_name' in mod and 'def_file' in mod and mod['def_file'] == mod['file_name']:
                    add_jump_definition(tree, tree_config, menu, mod)
                else:
                    add_jump_definition_to_line(tree, tree_config, menu, mod['def_file'], 1, "Jump to module defintion")
                    add_jump_definition(tree, tree_config, menu, mod, "Jump to module declaration")
            return (menu, None)

        # types masquerading as modules
        if datum['refid'] in tree.data.types:
            typ = tree.data.types[datum['refid']]
            menu = type_menu_generic(tree, typ, tree_config)
            add_jump_definition(tree, tree_config, menu, typ)
            title = None
            if 'value' in typ:
                title = typ['value']
            else:
                print "no value for", typ['kind'], typ['qualname']
            return (menu, truncate_value("", title))

    return None



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
            menu = []
            add_find_references(tree_config, menu, datum['qualname'], "module-alias-ref", "alias")
            add_jump_definition_to_line(tree, tree_config, menu, mod['def_file'], 1, "Jump to module defintion")
            return (menu, None)

    # 'module' aliases to types
    if datum['refid'] and datum['refid'] in tree.data.types:
        typ = tree.data.types[datum['refid']]
        if typ['name'] != datum['name']:
            menu = []
            add_find_references(tree_config, menu, datum['qualname'], "type-ref", "alias")
            add_jump_definition(tree, tree_config, menu, typ, "Jump to type declaration")
            return (menu, None)

    # 'module' aliases to variables
    if datum['refid'] and datum['refid'] in tree.data.variables:
        var = tree.data.variables[datum['refid']]
        if var['name'] != datum['name']:
            menu = []
            add_find_references(tree_config, menu, datum['qualname'], "var-ref", "alias")
            add_jump_definition(tree, tree_config, menu, var, "Jump to variable declaration")
            return (menu, None)

    # 'module' aliases to functions
    if datum['refid'] and datum['refid'] in tree.data.functions:
        fn = tree.data.functions[datum['refid']]
        if fn['name'] != datum['name']:
            menu = []
            add_find_references(tree_config, menu, datum['qualname'], "function-ref", "alias")
            add_jump_definition(tree, tree_config, menu, fn, "Jump to function declaration")
            return (menu, None)

    # extern crates to known local crates
    if 'location' in datum and datum['location'] and datum['location'] in tree.crates_by_name:
        crate = tree.crates_by_name[datum['location']]
        menu = []
        add_find_references(tree_config, menu, datum['qualname'], "module-alias-ref", "alias")
        add_jump_definition_to_line(tree, tree_config, menu, crate['file_name'], 1, "Jump to crate")
        return (menu, None)

    # extern crates to standard library crates
    if 'location' in datum and datum['location'] and datum['location'] in tree.locations:
        urls = tree.locations[datum['location']]
        menu = []
        add_find_references(tree_config, menu, datum['qualname'], "module-alias-ref", "alias")
        std_lib_links(tree_config, menu, urls)
        return (menu, None)

    # other references to standard library items
    if datum['refid'] in tree.data.unknowns:
        # FIXME We could probably do better and link to the precise type or static in docs etc., rather than just the crate
        urls = tree.locations[tree.data.unknowns[datum['refid']]['crate']]
        menu = []
        add_find_references(tree_config, menu, datum['qualname'], "module-alias-ref", "alias")
        std_lib_links(tree_config, menu, urls)
        return (menu, None)

    # extern mods to unknown local crates
    menu = []
    add_find_references(tree_config, menu, datum['qualname'], "module-alias-ref", "alias")
    return (menu, None)

    return None


def unknown_ref_menu(tree, datum, tree_config):
    if datum['refid'] and datum['refid'] in tree.data.unknowns:
        unknown = tree.data.unknowns[datum['refid']]
        menu = []
        add_find_references(tree_config, menu, str(datum['refid']), "extern-ref", "item")
        if unknown['crate'] in tree.locations:
            urls = tree.locations[unknown['crate']]
            std_lib_links(tree_config, menu, urls)
        return (menu, None)

    print "unknown unknown!"

    return None
