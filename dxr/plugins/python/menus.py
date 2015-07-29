from dxr.menus import SingleDatumMenuMaker
from dxr.utils import search_url


class _PythonPluginAttr(object):
    plugin = 'python'


class ClassMenuMaker(SingleDatumMenuMaker, _PythonPluginAttr):
    """Menu generator for class definitions"""

    def menu_items(self):
        qualname = self.data
        return [
            {'html': 'Find subclasses',
             'title': 'Find subclasses of this class',
             'href': search_url(self.tree, '+derived:' + qualname),
             'icon': 'type'},
            {'html': 'Find base classes',
             'title': 'Find base classes of this class',
             'href': search_url(self.tree, '+bases:' + qualname),
             'icon': 'type'},
        ]
