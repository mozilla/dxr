"""Cross-references for C/C++"""

from os.path import basename

from dxr.lines import Ref
from dxr.utils import browse_file_url, search_url


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
                     'href': browse_file_url(self.tree.name, path, _anchor=row),
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
               'href': browse_file_url(self.tree.name, self.menu_data),
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
               'href': search_url(self.tree.name, '+macro-ref:%s' % macro_name),
               'title': 'Find references to macros with this name',
               'icon': 'reference'}


class TypeRef(_QualnameRef):
    @classmethod
    def _condensed_menu_data(cls, tree, prop):
        return (super(TypeRef, cls)._condensed_menu_data(tree, prop) +
                (prop.get('kind', 'type'), 'has_subclass' in prop, 'has_base_class' in prop))

    def _more_menu_items(self, (qualname, kind, has_subclass, has_base_class)):
        """Return menu for type reference."""
        def kind_plural():
            if kind == 'class':
                return 'classes'
            elif kind == 'struct':
                return 'structs'
            else:
                return 'types'

        yield {'html': "Find declarations",
               'title': "Find declarations of this %s" % kind,
               'href': search_url(self.tree.name, "+type-decl:%s" % quote(qualname)),
               'icon': 'reference'}
        if has_subclass:
            kinds = kind_plural()
            yield {'html': "Find sub%s" % kinds,
                   'title': "Find sub%s of this %s" % (kinds, kind),
                   'href': search_url(self.tree.name, "+derived:%s" % quote(qualname)),
                   'icon': 'type'}
        if has_base_class:
            kinds = kind_plural()
            yield {'html': "Find base %s" % kinds,
                   'title': "Find base %s of this %s" % (kinds, kind),
                   'href': search_url(self.tree.name, "+bases:%s" % quote(qualname)),
                   'icon': 'type'}
        yield {'html': "Find members",
               'title': "Find members of this %s" % kind,
               'href': search_url(self.tree.name, "+member:%s" % quote(qualname)),
               'icon': 'members'}
        yield {'html': "Find references",
               'title': "Find references to this %s" % kind,
               'href': search_url(self.tree.name, "+type-ref:%s" % quote(qualname)),
               'icon': 'reference'}


class TypedefRef(_QualnameRef):
    def _more_menu_items(self, (qualname,)):
        yield {'html': "Find references",
               'title': "Find references to this typedef",
               'href': search_url(self.tree.name, "+type-ref:%s" % quote(qualname)),
               'icon': 'reference'}


class VariableRef(_QualnameRef):
    def _more_menu_items(self, (qualname,)):
        yield {'html': "Find declarations",
               'title': "Find declarations of this variable",
               'href': search_url(self.tree.name, "+var-decl:%s" % quote(qualname)),
               'icon': 'reference'}
        yield {'html': "Find references",
               'title': "Find reference to this variable",
               'href': search_url(self.tree.name, "+var-ref:%s" % quote(qualname)),
               'icon': 'field'}


class NamespaceRef(_QualnameRef):
    def _more_menu_items(self, (qualname,)):
        yield {'html': "Find definitions",
               'title': "Find definitions of this namespace",
               'href': search_url(self.tree.name, "+namespace:%s" % quote(qualname)),
               'icon': 'jump'}
        yield {'html': "Find references",
               'title': "Find references to this namespace",
               'href': search_url(self.tree.name, "+namespace-ref:%s" % quote(qualname)),
               'icon': 'reference'}


class NamespaceAliasRef(_QualnameRef):
    def _more_menu_items(self, (qualname,)):
        """Build menu for a namespace."""
        yield {'html': "Find references",
               'title': "Find references to this namespace alias",
               'href': search_url(self.tree.name, "+namespace-alias-ref:%s" % quote(qualname)),
               'icon': 'reference'}


class FunctionRef(_ClangRef):
    """Ref for function definitions or references"""

    @classmethod
    def from_condensed(cls, tree, prop):
        # We ignore the def location clang gives us since it can be wrong, but
        # its existence means this ref isn't itself a def.
        search_for_def = prop.get('defloc') is not None
        return cls(tree,
                   (search_for_def, prop['qualname'],
                    'has_overriddens' in prop, 'has_overrides' in prop),
                   qualname=prop['qualname'])

    def menu_items(self):
        search_for_def, qualname = self.menu_data[:2]
        if search_for_def:
            menu = [{'html': "Jump to definition",
                     'title': "Jump to definition",
                     'href': '%s&%s' % (search_url(self.tree.name,
                                                   '+function:%s' % quote(qualname)),
                                        'redirect=true'),
                     'icon': 'jump'}]
        else:
            menu = []
        menu.extend(self._more_menu_items())
        return menu

    def _more_menu_items(self):
        qualname, has_overriddens, has_overrides = self.menu_data[1:]
        qualname = quote(qualname)
        tree = self.tree.name
        yield {'html': "Find declarations",
               'title': "Find declarations of this function",
               'href': search_url(tree, "+function-decl:%s" % qualname),
               'icon': 'reference'}
        yield {'html': "Find callers",
               'title': "Find functions that call this function",
               'href': search_url(tree, "+callers:%s" % qualname),
               'icon': 'method'}
        yield {'html': "Find references",
               'title': "Find references to this function",
               'href': search_url(tree, "+function-ref:%s" % qualname),
               'icon': 'reference'}
        if has_overriddens:
            yield {'html': "Find overridden",
                   'title': "Find functions that this function overrides",
                   'href': search_url(tree, "+overridden:%s" % qualname),
                   'icon': 'method'}
        if has_overrides:
            yield {'html': "Find overrides",
                   'title': "Find overrides of this function",
                   'href': search_url(tree, "+overrides:%s" % qualname),
                   'icon': 'method'}
