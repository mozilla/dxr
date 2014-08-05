"""All menu constructors for the C/CXX refs."""
from dxr.utils import search_url


def quote(qualname):
    """ Wrap qualname in quotes if it contains spaces """
    if ' ' in qualname:
        qualname = '"' + qualname + '"'
    return qualname


def search(tree, query):
    """ Auxiliary function for getting the search url for query """
    return search_url(tree.config.wwwroot, tree.name, query)


def include_menu(tree, include):
    """Return menu for include reference."""
    (path, _, _), _ = include['span']
    return {
        'html': 'Jump to file',
        'title': 'Jump to what is included here.',
        'href': tree.config.wwwroot + '/' + tree.name + '/source/' + path,
        'icon': 'jump'
    }


def macro_menu(tree, macro):
    """Return menu for macro reference."""
    name = macro['name']
    return {
        'html': "Find references",
        'title': "Find references to macros with this name",
        'href': search(tree, "+macro-ref:%s" % name),
        'icon': 'reference'
    }


def type_menu(tree, type_):
    """Return menu for type reference."""
    qualname, kind = type_['qualname'], type_['kind']
    menu = []
    # Things we can do with qualname
    menu.append({
        'html': "Find declarations",
        'title': "Find declarations of this class",
        'href': search(tree, "+type-decl:%s" % quote(qualname)),
        'icon': 'reference'
    })
    if kind == 'class' or kind == 'struct':
        menu.append({
            'html': "Find sub classes",
            'title': "Find sub classes of this class",
            'href': search(tree, "+derived:%s" % quote(qualname)),
            'icon': 'type'
        })
        menu.append({
            'html': "Find base classes",
            'title': "Find base classes of this class",
            'href': search(tree, "+bases:%s" % quote(qualname)),
            'icon': 'type'
        })
    menu.append({
        'html': "Find members",
        'title': "Find members of this class",
        'href': search(tree, "+member:%s" % quote(qualname)),
        'icon': 'members'
    })
    menu.append({
        'html': "Find references",
        'title': "Find references to this class",
        'href': search(tree, "+type-ref:%s" % quote(qualname)),
        'icon': 'reference'
    })
    return menu

def typedef_menu(tree, typedef):
    """ Build menu for typedef """
    qualname = typedef['qualname']
    menu = []
    menu.append({
        'html': "Find references",
        'title': "Find references to this typedef",
        'href': search(tree, "+type-ref:%s" % quote(qualname)),
        'icon': 'reference'
    })
    return menu

def variable_menu(tree, variable):
    """ Build menu for a variable """
    qualname = variable['qualname']
    menu = []
    menu.append({
        'html': "Find declarations",
        'title': "Find declarations of this variable",
        'href': search(tree, "+var-decl:%s" % quote(qualname)),
        'icon': 'reference'
    })
    menu.append({
        'html': "Find references",
        'title': "Find reference to this variable",
        'href': search(tree, "+var-ref:%s" % quote(qualname)),
        'icon': 'field'
    })
    return menu

def namespace_menu(tree, namespace):
    """ Build menu for a namespace """
    qualname = namespace['qualname']
    menu = []
    menu.append({
        'html': "Find definitions",
        'title': "Find definitions of this namespace",
        'href': search(tree, "+namespace:%s" % quote(qualname)),
        'icon': 'jump'
    })
    menu.append({
        'html': "Find references",
        'title': "Find references to this namespace",
        'href': search(tree, "+namespace-ref:%s" % quote(qualname)),
        'icon': 'reference'
    })
    return menu

def namespace_alias_menu(tree, namespace_alias):
    """ Build menu for a namespace """
    qualname = namespace_alias['qualname']
    menu = []
    menu.append({
        'html': "Find references",
        'title': "Find references to this namespace alias",
        'href': search(tree, "+namespace-alias-ref:%s" % quote(qualname)),
        'icon': 'reference'
    })
    return menu


def function_menu(tree, func):
    """ Build menu for a function """
    qualname = func['qualname']
    isvirtual = 'override' in func
    menu = []
    # Things we can do with qualified name
    menu.append({
        'html': "Find declarations",
        'title': "Find declarations of this function",
        'href': search(tree, "+function-decl:%s" % quote(qualname)),
        'icon': 'reference'
    })
    menu.append({
        'html': "Find callers",
        'title': "Find functions that call this function",
        'href': search(tree, "+callers:%s" % quote(qualname)),
        'icon': 'method'
    })
    menu.append({
        'html': "Find callees",
        'title': "Find functions that are called by this function",
        'href': search(tree, "+called-by:%s" % quote(qualname)),
        'icon': 'method'
    })
    menu.append({
        'html': "Find references",
        'title': "Find references to this function",
        'href': search(tree, "+function-ref:%s" % quote(qualname)),
        'icon': 'reference'
    })
    if isvirtual:
        menu.append({
            'html': "Find overridden",
            'title': "Find functions that this function overrides",
            'href': search(tree, "+overridden:%s" % quote(qualname)),
            'icon': 'method'
        })
        menu.append({
            'html': "Find overrides",
            'title': "Find overrides of this function",
            'href': search(tree, "+overrides:%s" % quote(qualname)),
            'icon': 'method'
        })
    return menu
