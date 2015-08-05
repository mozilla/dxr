from dxr.lines import Ref
from dxr.utils import search_url


class _PythonPluginAttr(object):
    plugin = 'python'


class ClassRef(Ref, _PythonPluginAttr):
    """A reference attached to a class definition"""

    def menu_items(self):
        qualname = self.menu_data
        yield {'html': 'Find subclasses',
               'title': 'Find subclasses of this class',
               'href': search_url(self.tree, '+derived:' + qualname),
               'icon': 'type'}
        yield {'html': 'Find base classes',
               'title': 'Find base classes of this class',
               'href': search_url(self.tree, '+bases:' + qualname),
               'icon': 'type'}
