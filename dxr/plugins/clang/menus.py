"""Cross-references for C/C++"""

from os.path import basename

from flask import url_for

from dxr.app import DXR_BLUEPRINT
from dxr.lines import Ref
from dxr.utils import search_url, BROWSE


def quote(qualname):
    """Wrap qualname in quotes if it contains spaces."""
    if ' ' in qualname:
        qualname = '"' + qualname + '"'
    return qualname


class _ClangRef(Ref):
    plugin = 'clang'


class _RefWithDefinition(_ClangRef):
    """Abstract superclass which prepends a jump-to-definition menu to a Ref"""

    @classmethod
    def from_condensed(cls, tree, prop):
        """Return a tuple used to reconstitute a jump-to-definition menu,
        prepended onto whatever tuple the subclass returns from
        _condensed_menu_data().

        Also yank a qualname out of prop['qualname'] if available.

        """
        definition = prop.get('defloc')
        # If we can look up the target of this ref and it's not outside the
        # source tree (which results in an absolute path starting with "/")...
        if definition and not definition[0].startswith('/'):
            definition_tuple = definition[0], definition[1].row  # path, row
        else:
            definition_tuple = None, None
        return cls(tree,
                   (definition_tuple + cls._condensed_menu_data(tree, prop)),
                   qualname=prop.get('qualname'))

    def menu_items(self):
        """Return a jump-to-definition menu item along with whatever others
        _more_menu_items() returns.

        """
        path, row = self.menu_data[:2]
        if path is None:
            menu = []
        else:
            menu = [{'html': "Jump to definition",
                     'title': "Jump to the definition in '%s'" % basename(path),
                     'href': url_for(BROWSE, tree=self.tree.name, path=path, _anchor=row),
                     'icon': 'jump'}]
        menu.extend(self._more_menu_items(self.menu_data[2:]))
        return menu

    @classmethod
    def _condensed_menu_data(cls, tree, prop):
        """Return a tuple of menu data to persist, beyond what's needed for
        the definition menu."""
        raise NotImplementedError

    def _more_menu_items(self, menu_data):
        """Yield additional menu items, beyond the Jump To Definition one.

        :arg menu_data: The tuple of menu data returned from
            ``_condensed_menu_data``

        """
        raise NotImplementedError


class _QualnameRef(_RefWithDefinition):
    """A Ref that hangs onto only the "qualname" key from the condensed
    analysis info (along with whatever _RefWithDefinition hangs onto)"""
    @classmethod
    def _condensed_menu_data(cls, tree, prop):
        return prop['qualname'],


class IncludeRef(_ClangRef):
    """Cross-reference for file inclusions"""

    @classmethod
    def from_condensed(cls, tree, prop):
        return cls(tree, prop['target_path'])

    def menu_items(self):
        # TODO: Check against the ignore patterns, and don't link to files we
        # won't build pages for.
        yield {'html': 'Jump to file',
               'title': 'Jump to what is included here.',
               'href': url_for(BROWSE,
                               tree=self.tree.name,
                               path=self.menu_data),
               'icon': 'jump'}


class MacroRef(_RefWithDefinition):
    @classmethod
    def from_condensed(cls, tree, prop):
        new = super(MacroRef, cls).from_condensed(tree, prop)
        new.hover = prop.get('text')
        return new

    @classmethod
    def _condensed_menu_data(cls, tree, prop):
        return prop['name'],

    def _more_menu_items(self, (macro_name,)):
        yield {'html': 'Find references',
               'href': search_url(self.tree, '+macro-ref:%s' % macro_name),
               'title': 'Find references to macros with this name',
               'icon': 'reference'}


class TypeRef(_QualnameRef):
    @classmethod
    def _condensed_menu_data(cls, tree, prop):
        """Hang onto qualname *and* kind."""
        return (super(TypeRef, cls)._condensed_menu_data(tree, prop) +
                (prop.get('kind', ''),))

    def _more_menu_items(self, (qualname, kind)):
        """Return menu for type reference."""
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


class TypedefRef(_QualnameRef):
    def _more_menu_items(self, (qualname,)):
        yield {'html': "Find references",
               'title': "Find references to this typedef",
               'href': search_url(self.tree, "+type-ref:%s" % quote(qualname)),
               'icon': 'reference'}


class VariableRef(_QualnameRef):
    def _more_menu_items(self, (qualname,)):
        yield {'html': "Find declarations",
               'title': "Find declarations of this variable",
               'href': search_url(self.tree, "+var-decl:%s" % quote(qualname)),
               'icon': 'reference'}
        yield {'html': "Find references",
               'title': "Find reference to this variable",
               'href': search_url(self.tree, "+var-ref:%s" % quote(qualname)),
               'icon': 'field'}


class NamespaceRef(_QualnameRef):
    def _more_menu_items(self, (qualname,)):
        yield {'html': "Find definitions",
               'title': "Find definitions of this namespace",
               'href': search_url(self.tree, "+namespace:%s" % quote(qualname)),
               'icon': 'jump'}
        yield {'html': "Find references",
               'title': "Find references to this namespace",
               'href': search_url(self.tree, "+namespace-ref:%s" % quote(qualname)),
               'icon': 'reference'}


class NamespaceAliasRef(_QualnameRef):
    def _more_menu_items(self, (qualname,)):
        """Build menu for a namespace."""
        yield {'html': "Find references",
               'title': "Find references to this namespace alias",
               'href': search_url(self.tree, "+namespace-alias-ref:%s" % quote(qualname)),
               'icon': 'reference'}


class FunctionRef(_RefWithDefinition):
    """Ref for function definitions or references"""

    @classmethod
    def _condensed_menu_data(cls, tree, prop):
        return prop['qualname'], 'override' in prop

    def _more_menu_items(self, (qualname, is_virtual)):
        yield {'html': "Find declarations",
               'title': "Find declarations of this function",
               'href': search_url(self.tree, "+function-decl:%s" % quote(qualname)),
               'icon': 'reference'}
        yield {'html': "Find callers",
               'title': "Find functions that call this function",
               'href': search_url(self.tree, "+callers:%s" % quote(qualname)),
               'icon': 'method'}
        yield {'html': "Find references",
               'title': "Find references to this function",
               'href': search_url(self.tree, "+function-ref:%s" % quote(qualname)),
               'icon': 'reference'}
        if is_virtual:
            yield {'html': "Find overridden",
                   'title': "Find functions that this function overrides",
                   'href': search_url(self.tree, "+overridden:%s" % quote(qualname)),
                   'icon': 'method'}
            yield {'html': "Find overrides",
                   'title': "Find overrides of this function",
                   'href': search_url(self.tree, "+overrides:%s" % quote(qualname)),
                   'icon': 'method'}
