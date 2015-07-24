from dxr.utils import search_url


def class_menu(tree, qualname):
    """Generate menu for a class definition."""
    return [
        {'html': 'Find subclasses',
         'title': 'Find subclasses of this class',
         'href': search_url(tree, '+derived:' + qualname),
         'icon': 'type'},
        {'html': 'Find base classes',
         'title': 'Find base classes of this class',
         'href': search_url(tree, '+bases:' + qualname),
         'icon': 'type'},
    ]


def function_ref_menu(tree, name):
    """Generate menu for function references."""
    return {
        'html': 'Find references',
        'title': 'Find references to this function',
        'href': search_url(tree, 'ref:' + name),
        'icon': 'method'
    }


def function_id_menu(tree, name):
    """Generate menu for a search for function definition."""
    return {
        'html': 'Find definition',
        'title': 'Find definition of this function',
        'href': search_url(tree, 'id:' + name),
        'icon': 'method'
    }
