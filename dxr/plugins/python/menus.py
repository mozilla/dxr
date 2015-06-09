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
