from dxr.lines import Ref
from dxr.utils import search_url


PLUGIN_NAME = 'js'


class _JsRef(Ref):
    plugin = PLUGIN_NAME


class QualifiedRef(_JsRef):
    """Ref that yields a menu option for id and ref of (qualname, name, typename).
    """
    def menu_items(self):
        qualname, name, typename = self.menu_data
        for text, filtername, title, icon in [
                ("Find definition of %s %s" % (typename, name), "id", "Find definition", "class"),
                ("Find references to %s %s" % (typename, name), "ref", "Find references", "method")]:
            yield {
                'html': text,
                'title': title,
                'href': search_url(self.tree.name, '+%s:"%s"' % (filtername, qualname)),
                'icon': icon
            }

