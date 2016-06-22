from dxr.utils import search_url
from dxr.lines import Ref


PLUGIN_NAME = 'xbl'


class _XblRef(Ref):
    plugin = PLUGIN_NAME


class TypeRef(_XblRef):
    """Ref that yields a menu option for search on type and type-decl.
    """
    def menu_items(self):
        name = self.menu_data
        for text, filtername, title, icon in [
                ("Find declaration of %s" % (name), "type-decl", "Find declaration", "reference"),
                ("Find definition of %s" % (name), "type", "Find definition", "type")]:
            yield {
                'html': text,
                'title': title,
                'href': search_url(self.tree.name, '%s:"%s"' % (filtername, name)),
                'icon': icon
            }
