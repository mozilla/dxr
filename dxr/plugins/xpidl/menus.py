from flask import url_for

from dxr.utils import search_url


def filtered_search_menu(tree, term, html, title, filter_name, icon):
    """Return a menu for searching in given tree for a specific term using a filter."""

    return {
        'html': html,
        'title': title,
        'href': search_url(tree, '%s:%s' % (filter_name, term)),
        'icon': icon
    }


def generated_menu(url, line):
    """Return a menu for jumping to corresponding C++ source using the line map."""

    return {
        'html': 'See generated source',
        'title': 'Go to this line in the generated C++ header file',
        'href': url + '#%d' % line,
        'icon': 'jump'
    }


def include_menu(tree, path):
    """Return a menu for linking to another file in an include directive."""

    return {
        'html': 'Jump to file',
        'title': 'Go to the target of the include statement',
        'href': url_for('.browse', tree=tree.name, path=path),
        'icon': 'jump'
    }


_decl_text = ('Find declaration', 'Search for declarations.')
_def_text = ('Find definition', 'Search for definitions.')

# Follow the schema (html, title, filter name, icon)
subclass_menu = ('Find subclasses', 'Search for children of this interface.', 'derived', 'class')

type_menu = _def_text + ('type', 'reference')
typedecl_menu = _decl_text + ('type-decl', 'type')

var_menu = _def_text + ('var', 'field')
vardecl_menu = _decl_text + ('var-decl', 'field')

function_menu = _decl_text + ('function-decl', 'method')
functiondecl_menu = ('Find overrides', 'Search for overrides of this method.', 'function', 'method')
