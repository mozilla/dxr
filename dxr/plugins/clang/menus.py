"""All menu constructors for the C/C++ refs."""

from os.path import basename

from flask import url_for

from dxr.app import DXR_BLUEPRINT
from dxr.menus import MenuMaker, SingleDatumMenuMaker
from dxr.utils import search_url, without_ending


BROWSE = DXR_BLUEPRINT + '.browse'


def quote(qualname):
    """Wrap qualname in quotes if it contains spaces."""
    if ' ' in qualname:
        qualname = '"' + qualname + '"'
    return qualname


class _ClangPluginAttr(object):
    plugin = 'clang'


class _QualnameMenuMaker(SingleDatumMenuMaker):
    """A menu maker that hangs onto only the "qualname" key from the condensed
    analysis info"""
    @classmethod
    def from_condensed(cls, tree, condensed):
        return cls(tree, condensed['qualname'])


class IncludeMenuMaker(SingleDatumMenuMaker, _ClangPluginAttr):
    @classmethod
    def from_condensed(cls, tree, condensed):
        return cls(tree, condensed['target_path'])

    def menu_items(self):
        """Return menu for include reference."""
        # TODO: Check against the ignore patterns, and don't link to files we
        # won't build pages for.
        yield {'html': 'Jump to file',
               'title': 'Jump to what is included here.',
               'href': url_for(BROWSE,
                               tree=self.tree.name,
                               path=self.data),
               'icon': 'jump'}


class MacroMenuMaker(SingleDatumMenuMaker, _ClangPluginAttr):
    @classmethod
    def from_condensed(cls, tree, condensed):
        return cls(tree, condensed['name'])

    def menu_items(self):
        yield {'html': 'Find references',
               'href': search_url(self.tree, '+macro-ref:%s' % self.data),
               'title': 'Find references to macros with this name',
               'icon': 'reference'}


class TypeMenuMaker(SingleDatumMenuMaker, _ClangPluginAttr):
    @classmethod
    def from_condensed(cls, tree, condensed):
        return cls(tree, (condensed['qualname'], condensed.get('kind', '')))

    def menu_items(self):
        """Return menu for type reference."""
        qualname, kind = self.data
        yield {'html': "Find declarations",
               'title': "Find declarations of this class",
               'href': search_url(self.tree, "+type-decl:%s" % quote(qualname)),
               'icon': 'reference'}
        if kind == 'class' or kind == 'struct':
            yield {'html': "Find subclasses",
                   'title': "Find subclasses of this class",
                   'href': search_url(self.tree, "+derived:%s" % quote(qualname)),
                   'icon': 'type'}
            yield {'html': "Find base classes",
                   'title': "Find base classes of this class",
                   'href': search_url(self.tree, "+bases:%s" % quote(qualname)),
                   'icon': 'type'}
        yield {'html': "Find members",
               'title': "Find members of this class",
               'href': search_url(self.tree, "+member:%s" % quote(qualname)),
               'icon': 'members'}
        yield {'html': "Find references",
               'title': "Find references to this class",
               'href': search_url(self.tree, "+type-ref:%s" % quote(qualname)),
               'icon': 'reference'}


class TypedefMenuMaker(_QualnameMenuMaker, _ClangPluginAttr):
    def menu_items(self):
        """Build menu for typedef."""
        yield {'html': "Find references",
               'title': "Find references to this typedef",
               'href': search_url(self.tree, "+type-ref:%s" % quote(self.data)),
               'icon': 'reference'}


class VariableMenuMaker(_QualnameMenuMaker, _ClangPluginAttr):
    def menu_items(self):
        """Build menu for a variable."""
        yield {'html': "Find declarations",
               'title': "Find declarations of this variable",
               'href': search_url(self.tree, "+var-decl:%s" % quote(self.data)),
               'icon': 'reference'}
        yield {'html': "Find references",
               'title': "Find reference to this variable",
               'href': search_url(self.tree, "+var-ref:%s" % quote(self.data)),
               'icon': 'field'}


class NamespaceMenuMaker(_QualnameMenuMaker, _ClangPluginAttr):
    def menu_items(self):
        """Build menu for a namespace."""
        yield {'html': "Find definitions",
               'title': "Find definitions of this namespace",
               'href': search_url(self.tree, "+namespace:%s" % quote(self.data)),
               'icon': 'jump'}
        yield {'html': "Find references",
               'title': "Find references to this namespace",
               'href': search_url(self.tree, "+namespace-ref:%s" % quote(self.data)),
               'icon': 'reference'}


class NamespaceAliasMenuMaker(_QualnameMenuMaker, _ClangPluginAttr):
    def menu_items(self):
        """Build menu for a namespace."""
        yield {'html': "Find references",
               'title': "Find references to this namespace alias",
               'href': search_url(self.tree, "+namespace-alias-ref:%s" % quote(self.data)),
               'icon': 'reference'}


class FunctionMenuMaker(SingleDatumMenuMaker, _ClangPluginAttr):
    """Menu builder for function definitions or references"""

    @classmethod
    def from_condensed(cls, tree, condensed):
        return cls(tree, (condensed['qualname'], 'override' in condensed))

    def menu_items(self):
        qualname, is_virtual = self.data
        # Things we can do with qualified name
        menu = [{'html': "Find declarations",
                 'title': "Find declarations of this function",
                 'href': search_url(self.tree, "+function-decl:%s" % quote(qualname)),
                 'icon': 'reference'},
                {'html': "Find callers",
                 'title': "Find functions that call this function",
                 'href': search_url(self.tree, "+callers:%s" % quote(qualname)),
                 'icon': 'method'},
                {'html': "Find references",
                 'title': "Find references to this function",
                 'href': search_url(self.tree, "+function-ref:%s" % quote(qualname)),
                 'icon': 'reference'}]
        if is_virtual:
            menu.append({'html': "Find overridden",
                         'title': "Find functions that this function overrides",
                         'href': search_url(self.tree, "+overridden:%s" % quote(qualname)),
                         'icon': 'method'})
            menu.append({'html': "Find overrides",
                         'title': "Find overrides of this function",
                         'href': search_url(self.tree, "+overrides:%s" % quote(qualname)),
                         'icon': 'method'})
        return menu


class DefinitionMenuMaker(MenuMaker, _ClangPluginAttr):
    """A one-item menu for jumping directly to something's definition"""

    def __init__(self, tree, path, row):
        super(DefinitionMenuMaker, self).__init__(tree)
        self.path = path
        self.row = row

    def es(self):
        return self.path, self.row

    @classmethod
    def from_es(cls, tree, data):
        return cls(tree, *data)

    def menu_items(self):
        yield {'html': "Jump to definition",
               'title': "Jump to the definition in '%s'" % basename(self.path),
               'href': url_for(BROWSE, tree=self.tree.name, path=self.path, _anchor=self.row),
               'icon': 'jump'}
