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
                          unsparsify)
from dxr.plugins.clang.condense import condense_file, inheritance_and_overrides
from dxr.plugins.clang.menus import (function_menu, variable_menu, type_menu,
                                     namespace_menu, namespace_alias_menu,
                                     macro_menu, include_menu, typedef_menu,
                                     definition_menu)
from dxr.plugins.clang.needles import all_needles


PLUGIN_NAME = 'clang'


# An unanlyzed string property that points to a value that can be exact- or
# prefix-matched against and carries start/end bounds for highlighting. Has
# both a name and a qualname.
QUALIFIED_NEEDLE = {
    'type': 'object',
    'properties': {
        'name': {
            'type': 'string',
            'index': 'not_analyzed',
            'fields': {
                'lower': {
                    'type': 'string',
                    'analyzer': 'lowercase'
                }
            }
        },
        'qualname': {
            'type': 'string',
            'index': 'not_analyzed'
        },
        'start': {
            'type': 'integer',
            'index': 'no'  # just for highlighting
        },
        'end': {
            'type': 'integer',
            'index': 'no'
        }
    }
}


mappings = {
    LINE: {
        'properties': {
            'c_function': QUALIFIED_NEEDLE,
            'c_function_ref': QUALIFIED_NEEDLE,
            'c_function_decl': QUALIFIED_NEEDLE,
            'c_type_ref': QUALIFIED_NEEDLE,
            'c_type_decl': QUALIFIED_NEEDLE,
            'c_type': QUALIFIED_NEEDLE,
            'c_var': QUALIFIED_NEEDLE,
            'c_var_ref': QUALIFIED_NEEDLE,
            'c_var_decl': QUALIFIED_NEEDLE,
            'c_macro': QUALIFIED_NEEDLE,
            'c_macro_ref': QUALIFIED_NEEDLE,
            'c_namespace': QUALIFIED_NEEDLE,
            'c_namespace_ref': QUALIFIED_NEEDLE,
            'c_namespace_alias': QUALIFIED_NEEDLE,
            'c_namespace_alias_ref': QUALIFIED_NEEDLE,
            'c_warning': QUALIFIED_NEEDLE,
            'c_warning_opt': QUALIFIED_NEEDLE,
            'c_call': QUALIFIED_NEEDLE,
            'c_bases': QUALIFIED_NEEDLE,
            'c_derived': QUALIFIED_NEEDLE,
            'c_member': QUALIFIED_NEEDLE,
            'c_overrides': QUALIFIED_NEEDLE,
            'c_overridden': QUALIFIED_NEEDLE
        }
    }
}


class FileToIndex(FileToIndexBase):
    """C and C++ indexer using clang compiler plugin"""

    def __init__(self, path, contents, tree, inherit):
        super(FileToIndex, self).__init__(path, contents, tree)
        self.inherit = inherit
        self.condensed = condense_file(*os.path.split(path))

    def needles_by_line(self):
        return all_needles(self.condensed,
                           self.inherit)

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
            self.tree.config.wwwroot)  # TODO: DRY
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
                if 'declloc' in prop:  # if we can look up the target of this ref
                    menu = definition_menu(self.tree,
                                           path=prop['declloc'][0],
                                           row=prop['declloc'][1].row)
                else:
                    menu = []

                menu.extend(menu_maker(self.tree, prop))
                start, end = prop['span']

                if start.offset is None or end.offset is None:
                    raise NotImplementedError("Fix this logic. It's full of holes. We must return a file-wide offset, but Position.offset was None.")
                yield start.offset, end.offset, (menu, tooltip(prop))

    def links(self):
        # For each type add a section with members

        getter = itemgetter('name', 'qualname', 'span', 'kind')
        for name, tid, span, kind in imap(getter, self.condensed['type']):
            (_, line, _), _ = span
            if len(name) == 0:
                continue

            # Make sure we have a sane limitation of kind
            if kind not in ('class', 'struct', 'enum', 'union'):
                print >> sys.stderr, "kind '%s' was replaced for 'type'!" % kind
                kind = 'type'

            links = chain(_members(self.condensed, 'function', tid),
                          _members(self.condensed, 'variable', tid))

            links = sorted(links, key=itemgetter(1))  # by line

            # Add the outer type as the first link
            links = [(kind, name, "#%s" % line)] + links

            yield 30, name, links

        # Add all macros to the macro section
        links = []
        getter = itemgetter('name', 'span')
        for name, span in imap(getter, self.condensed['type']):
            (_, line, _), _ = span
            links.append(('macro', name, "#%s" % line))
        if links:
            yield 100, "Macros", links


@autocurry
def kind_getter(field, kind, condensed):
    """Reach into a field and filter based on the kind."""
    return (ref for ref in condensed.get(field) if ref['kind'] == kind)


def _members(condensed, key, id_):
    """Fetch member {{key}} given a type id."""
    pred = lambda x: id_ == x['qualname']
    for props in ifilter(pred, condensed[key]):
        # Skip nameless things
        name = props['qualname']
        (_, line, _), _ = props['span']
        if not name:
            continue
        yield 'method', name, "#%s" % line


class TreeToIndex(TreeToIndexBase):
    def environment(self, vars_):
        """Set up environment variables to trigger analysis dumps from clang.

        We'll store all the havested metadata in the plugins temporary folder.

        """
        tree = self.tree
        temp_folder = os.path.join(tree.temp_folder, 'plugins', PLUGIN_NAME)
        self._temp_folder = temp_folder
        plugin_folder = os.path.join(tree.config.plugin_folder, PLUGIN_NAME)
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
            'DXR_CXX_CLANG_TEMP_FOLDER': temp_folder,
        }
        env['DXR_CC'] = env['CC']
        env['DXR_CXX'] = env['CXX']
        return merge(vars_, env)

    def post_build(self):
        self._inheritance, self._overriddens = inheritance_and_overrides(self._temp_folder)

    def file_to_index(self, path, contents):
        return FileToIndex(os.path.join(
                self._temp_folder, path), contents, self.tree, self._inheritance)
