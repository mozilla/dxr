"""Common menu constructors for use in plugins."""
from os.path import basename

from dxr.utils import browse_url


def definition_menu(tree, path, row):
    """Return a one-item menu for jumping directly to something's definition."""
    return [{'html': "Jump to definition",
             'title': "Jump to the definition in '%s'" % basename(path),
             'href': browse_url(tree=tree.name, path=path, line=row),
             'icon': 'jump'}]
