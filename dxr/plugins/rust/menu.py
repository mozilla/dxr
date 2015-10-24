import os
from functools import partial
from warnings import warn

from flask import url_for

from dxr.utils import BROWSE, search_url


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


def find_references_menu_item(tree_config, qualname, filter_name, kind):
    """A sort of compound menu that handles finding various sorts of
    references

    Should be broken into several.

    """
    return {'html':   "Find references",
            'title':  "Find references to this " + kind,
            'href':   search_url(tree_config, "+" + filter_name + ":%s" % quote(qualname)),
            'icon':   'reference'}


def std_lib_links_menu((doc_url, src_url, dxr_url), extra_text=""):
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


def call_menu(qualname, tree):
    return [{'html': "Find callers",
             'title': "Find calls of this function",
             'href': search_url(tree, "+callers:%s" % quote(qualname)),
             'icon': 'method'}]


def generic_function_menu(qualname, tree_config):
    """Return menu makers shared by function def/decls and function refs."""

    menu = call_menu(qualname, tree_config)
    menu.append(find_references_menu_item(tree_config, qualname, "function-ref", "function"))
    return menu


def jump_to_target_menu_item(tree_config, path, row, target_name):
    """Make a menu that jumps straight to a specific line of a file."""

    return {'html': 'Jump to %s' % target_name,
            'title': "Jump to %s in '%s'" % (target_name,
                                             os.path.basename(path)),
            'href': url_for(BROWSE, tree=tree_config.name, path=path, _anchor=row),
            'icon': 'jump'}

def jump_to_target_from_decl(menu_maker, tree, decl):
    """Return a jump menu item from a declaration mapping.

    If the incoming declaration doesn't warrant the creation of a menu,
    return None.
    """

    path = decl['file_name']
    if path:
        return menu_maker(tree, path, decl['file_line'])
    else:
        warn("Can't add jump to empty path.")  # Can this happen?


jump_to_trait_method_menu_item = partial(jump_to_target_menu_item, target_name='trait method')
jump_to_definition_menu_item = partial(jump_to_target_menu_item, target_name='definition')
jump_to_module_definition_menu_item = partial(jump_to_target_menu_item, target_name='module definition')
jump_to_module_declaration_menu_item = partial(jump_to_target_menu_item, target_name='module declaration')
jump_to_alias_definition_menu_item = partial(jump_to_target_menu_item, target_name='alias definition')
jump_to_crate_menu_item = partial(jump_to_target_menu_item, target_name='crate')
jump_to_type_declaration_menu_item = partial(jump_to_target_menu_item, target_name='type declaration')
jump_to_variable_declaration_menu_item = partial(jump_to_target_menu_item, target_name='variable declaration')
jump_to_function_declaration_menu_item = partial(jump_to_target_menu_item, target_name='function declaration')


def trait_impl_menu_item(tree_config, qualname, count):
    return {'html': "Find implementations (%d)" % count,
            'title': "Find implementations of this trait method",
            'href': search_url(tree_config, "+fn-impls:%s" % quote(qualname)),
            'icon': 'method'}


def generic_variable_menu(datum, tree_config):
    return [find_references_menu_item(tree_config, datum['qualname'], "var-ref", "variable")]


def type_menu(tree_config, kind, qualname):
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


def generic_type_menu(datum, tree_config):
    kind = datum['kind']
    qualname = datum['qualname']
    menu = list(type_menu(tree_config, kind, qualname))
    menu.append(find_references_menu_item(tree_config, qualname, "type-ref", kind))
    return menu


def use_items_menu_item(tree_config, qualname):
    return {'html': "Find use items",
            'title': "Find instances of this module in 'use' items",
            'href': search_url(tree_config, "+module-use:%s" % quote(qualname)),
            'icon': 'reference'}


def generic_module_menu(datum, tree_config):
    return [use_items_menu_item(tree_config, datum['qualname']),
            find_references_menu_item(tree_config, datum['qualname'], "module-ref", "module")]
