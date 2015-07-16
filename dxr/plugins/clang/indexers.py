from collections import defaultdict
import os
import sys
from operator import itemgetter
from itertools import chain, izip, ifilter
from functools import partial

from funcy import (merge, imap, group_by, is_mapping, repeat,
                   constantly, icat, autocurry)

from dxr.filters import LINE
from dxr.indexers import (FileToIndex as FileToIndexBase,
                          TreeToIndex as TreeToIndexBase,
                          QUALIFIED_LINE_NEEDLE, unsparsify, FuncSig, Ref)
from dxr.plugins.clang.condense import condense_file, condense_global
from dxr.plugins.clang.menus import (function_menu, variable_menu, type_menu,
                                     namespace_menu, namespace_alias_menu,
                                     macro_menu, include_menu, typedef_menu,
                                     definition_menu)
from dxr.plugins.clang.needles import all_needles


mappings = {
    LINE: {
        'properties': {
            'c_function': QUALIFIED_LINE_NEEDLE,
            'c_function_ref': QUALIFIED_LINE_NEEDLE,
            'c_function_decl': QUALIFIED_LINE_NEEDLE,
            'c_type_ref': QUALIFIED_LINE_NEEDLE,
            'c_type_decl': QUALIFIED_LINE_NEEDLE,
            'c_type': QUALIFIED_LINE_NEEDLE,
            'c_var': QUALIFIED_LINE_NEEDLE,
            'c_var_ref': QUALIFIED_LINE_NEEDLE,
            'c_var_decl': QUALIFIED_LINE_NEEDLE,
            'c_macro': QUALIFIED_LINE_NEEDLE,
            'c_macro_ref': QUALIFIED_LINE_NEEDLE,
            'c_namespace': QUALIFIED_LINE_NEEDLE,
            'c_namespace_ref': QUALIFIED_LINE_NEEDLE,
            'c_namespace_alias': QUALIFIED_LINE_NEEDLE,
            'c_namespace_alias_ref': QUALIFIED_LINE_NEEDLE,
            'c_warning': QUALIFIED_LINE_NEEDLE,
            'c_warning_opt': QUALIFIED_LINE_NEEDLE,
            'c_call': QUALIFIED_LINE_NEEDLE,
            'c_bases': QUALIFIED_LINE_NEEDLE,
            'c_derived': QUALIFIED_LINE_NEEDLE,
            'c_member': QUALIFIED_LINE_NEEDLE,
            'c_overrides': QUALIFIED_LINE_NEEDLE,
            # At a base method's site, record all the methods that override
            # it. Then we can search for any of those methods and turn up the
            # base one:
            'c_overridden': QUALIFIED_LINE_NEEDLE
        }
    }
}


class FileToIndex(FileToIndexBase):
    """C and C++ indexer using clang compiler plugin"""

    def __init__(self, path, contents, plugin_name, tree, overrides, overriddens, parents, children, temp_folder):
        super(FileToIndex, self).__init__(path, contents, plugin_name, tree)
        self.overrides = overrides
        self.overriddens = overriddens
        self.parents = parents
        self.children = children
        self.condensed = condense_file(temp_folder, path)

    def needles_by_line(self):
        return all_needles(
                self.condensed,
                self.overrides,
                self.overriddens,
                self.parents,
                self.children)

    def refs(self):
        def silent_itemgetter(y):
            return lambda x: x.get(y, [])

        # Refs are not structured much like functions, but they have a
        # qualname key, which is all that function_menu() requires, so we can
        # just chain kind_getters together with other getters.
        #
        # Menu makers and the thing-getters over which they run:
        menus_and_views = [
                (function_menu, [silent_itemgetter('function'),
                                 kind_getter('ref', 'function')]),
                (variable_menu, [silent_itemgetter('variable'),
                                 kind_getter('ref', 'variable')]),
                (type_menu, [silent_itemgetter('type'),
                             kind_getter('ref', 'type')]),
                (type_menu, [silent_itemgetter('decldef')]),
                (typedef_menu, [silent_itemgetter('typedef'),
                                kind_getter('ref', 'typedef')]),
                (namespace_menu, [silent_itemgetter('namespace'),
                                  kind_getter('ref', 'namespace')]),
                (namespace_alias_menu, [silent_itemgetter('namespace_alias'),
                                        kind_getter('ref', 'namespace_alias')]),
                (macro_menu,
                 [silent_itemgetter('macro'), kind_getter('ref', 'macro')],
                 silent_itemgetter('text')),
                (include_menu, [silent_itemgetter('include')])]
        return chain.from_iterable(self._refs_from_view(*mv) for mv in
                                   menus_and_views)

    @unsparsify
    def annotations_by_line(self):
        icon = "background-image: url('{0}/static/icons/warning.png');".format(
            self.tree.config.www_root)  # TODO: DRY
        getter = itemgetter('msg', 'opt', 'span')
        for msg, opt, span in imap(getter, self.condensed.get('warnings', [])):
            if opt:
                msg = "{0}[{1}]".format(msg, opt)
            annotation = {
                'title': msg,
                'class': "note note-warning",
                'style': icon
            }
            yield annotation, span

    def _refs_from_view(self, menu_maker, views, tooltip=constantly(None)):
        """Return an iterable of (start, end, (menu, tooltip)), running
        ``menu_maker`` across each item that comes of applying ``view`` to
        ``self.condensed`` and adding "Jump to definition" where applicable.

        :arg menu_maker: A function that takes a tree and an item from
            ``view()`` and returns a ref menu
        :arg views: An iterable of functions that take self.condensed and
            return an iterable of things to call ``menu_maker()`` on
        :arg tooltip: A function that takes one of those things from the
            iterable and emits a value to be shown in the mouseover of the ref

        """
        for prop in chain.from_iterable(v(self.condensed) for v in views):
            if 'span' in prop:  # TODO: This used to be unconditional. Should we still try to do it sometime if span isn't in prop? Both cases in test_direct are examples of this. [Marcell says no.]
                definition = prop.get('defloc')
                # If we can look up the target of this ref and it's not
                # outside the source tree (which results in an absolute path
                # starting with "/")...
                if definition and not definition[0].startswith('/'):
                    menu = definition_menu(self.tree,
                                           path=definition[0],
                                           row=definition[1].row)
                else:
                    menu = []

                menu.extend(menu_maker(self.tree, prop))
                start, end = prop['span']

                yield (self.char_offset(start.row, start.col),
                       self.char_offset(end.row, end.col),
                       Ref(menu, hover=tooltip(prop), qualname=prop.get('qualname')))

    def links(self):
        """Yield a section for each class, type, enum, etc., as well as one
        for macro definitions.

        """
        def get_scopes_to_members():
            """Return a hash of qualified-scope-of-type -> set-of-members."""
            ret = defaultdict(list)
            for member in chain(self.condensed['function'],
                                self.condensed['variable']):
                try:
                    scope, _ = member['qualname'].rsplit('::', 1)
                except ValueError:
                    # There was no ::, so this wasn't a member of anything.
                    pass
                else:
                    ret[scope].append(member)
            return ret

        scopes_to_members = get_scopes_to_members()

        # Spin around the types (enums, classes, unions, etc.):
        for type in self.condensed['type']:
            if type['name']:
                # First, link to the type definition itself:
                links = [(type['kind'],
                          type['name'],
                          '#%s' % type['span'].start.row)]
                # Look up the stuff with that scope in the hash, and spit out
                # names and line numbers, sorting by line number.
                members = list(scopes_to_members[type['qualname']])
                members.sort(key=lambda m: m['span'].start.row)
                links.extend(('method' if isinstance(m['type'], FuncSig)
                                       else 'field',  # icon
                              m['name'],
                              '#%s' % m['span'].start.row)
                             for m in members if m['name'])
                yield 30, type['name'], links

        # Add all macros to the macro section:
        links = [('macro', t['name'], '#%s' % t['span'].start.row)
                 for t in self.condensed['macro']]
        if links:
            yield 100, 'Macros', links


@autocurry
def kind_getter(field, kind, condensed):
    """Reach into a field and filter based on the kind."""
    return (ref for ref in condensed.get(field) if ref.get('kind') == kind)


class TreeToIndex(TreeToIndexBase):
    def pre_build(self):
        self._temp_folder = os.path.join(self.tree.temp_folder,
                                         'plugins',
                                         self.plugin_name)

    def environment(self, vars_):
        """Set up environment variables to trigger analysis dumps from clang.

        We'll store all the havested metadata in the plugins temporary folder.

        """
        tree = self.tree
        plugin_folder = os.path.dirname(__file__)
        flags = [
            '-load', os.path.join(plugin_folder, 'libclang-index-plugin.so'),
            '-add-plugin', 'dxr-index',
            '-plugin-arg-dxr-index', tree.source_folder
        ]
        flags_str = " ".join(imap('-Xclang {}'.format, flags))

        env = {
            'CC': "clang %s" % flags_str,
            'CXX': "clang++ %s" % flags_str,
            'DXR_CLANG_FLAGS': flags_str,
            'DXR_CXX_CLANG_OBJECT_FOLDER': tree.object_folder,
            'DXR_CXX_CLANG_TEMP_FOLDER': self._temp_folder,
        }
        env['DXR_CC'] = env['CC']
        env['DXR_CXX'] = env['CXX']
        return merge(vars_, env)

    def post_build(self):
        self._overrides, self._overriddens, self._parents, self._children = condense_global(self._temp_folder)

    def file_to_index(self, path, contents):
        return FileToIndex(path,
                           contents,
                           self.plugin_name,
                           self.tree,
                           self._overrides,
                           self._overriddens,
                           self._parents,
                           self._children,
                           self._temp_folder)
