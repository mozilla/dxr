from collections import defaultdict
from hashlib import sha1
from itertools import chain
from operator import itemgetter
import os
from os import listdir

from funcy import merge, imap, autocurry

from dxr.filters import LINE
from dxr.indexers import (FileToIndex as FileToIndexBase,
                          TreeToIndex as TreeToIndexBase,
                          QUALIFIED_LINE_NEEDLE, unsparsify, FuncSig)
from dxr.plugins.clang.condense import condense_file, condense_global
from dxr.plugins.clang.menus import (FunctionRef, VariableRef, TypeRef,
    NamespaceRef, NamespaceAliasRef, MacroRef, IncludeRef, TypedefRef)
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

    def __init__(self, path, contents, plugin_name, tree, overrides, overriddens, parents, children, csv_names, temp_folder):
        super(FileToIndex, self).__init__(path, contents, plugin_name, tree)
        self.overrides = overrides
        self.overriddens = overriddens
        self.parents = parents
        self.children = children
        self.condensed = condense_file(temp_folder, path,
                                       overrides, overriddens,
                                       parents, children,
                                       csv_names)

    def needles_by_line(self):
        return all_needles(
                self.condensed,
                self.overrides,
                self.overriddens,
                self.parents,
                self.children)

    def refs(self):
        def getter_or_empty(y):
            return lambda x: x.get(y, [])

        # Ref subclasses and the thing-getters that provide input to their
        # from_condensed() methods:
        classes_and_getters = [
            (FunctionRef, [getter_or_empty('function'),
                           kind_getter('decldef', 'function'),
                           # Refs are not structured much like functions, but
                           # they have a qualname key, which is all FunctionRef
                           # requires, so we can just chain kind_getters
                           # together with other getters.
                           kind_getter('ref', 'function')]),
            (VariableRef, [getter_or_empty('variable'),
                           kind_getter('ref', 'variable')]),
            (TypeRef, [getter_or_empty('type'),
                       kind_getter('ref', 'type'),
                       not_kind_getter('decldef', 'function')]),
            (TypedefRef, [getter_or_empty('typedef'),
                          kind_getter('ref', 'typedef')]),
            (NamespaceRef, [getter_or_empty('namespace'),
                            kind_getter('ref', 'namespace')]),
            (NamespaceAliasRef, [getter_or_empty('namespace_alias'),
                                 kind_getter('ref', 'namespace_alias')]),
            (MacroRef, [getter_or_empty('macro'),
                        kind_getter('ref', 'macro')]),
            (IncludeRef, [getter_or_empty('include')])]

        for ref_class, getters in classes_and_getters:
            for prop in chain.from_iterable(g(self.condensed) for g in getters):
                if 'span' in prop:
                    start, end = prop['span']
                    yield (self.char_offset(start.row, start.col),
                           self.char_offset(end.row, end.col),
                           ref_class.from_condensed(self.tree, prop))

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
    return (ref for ref in condensed.get(field, []) if ref.get('kind') == kind)


@autocurry
def not_kind_getter(field, kind, condensed):
    """Reach into a field and filter out those with given kind."""
    return (ref for ref in condensed.get(field, []) if ref.get('kind') != kind)



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
        def csv_map():
            """Map input files to the output CSVs corresponding to them.

            Return {path sha1: [file names (minus '.csv' extension)]}.

            This saves a lot of globbing later, which can add up to hours over
            the course of tens of thousands of files, depending on IO speed. An
            alternative approach might be a radix tree of folders: less RAM,
            more IO. Try that and bench it sometime.

            """
            ret = defaultdict(list)
            for csv_name in listdir(self._temp_folder):
                if csv_name.endswith('.csv'):
                    path_hash, content_hash, ext = csv_name.split('.')
                    # Removing ".csv" saves at least 2MB per worker on 700K files:
                    ret[path_hash].append(csv_name[:-4])
            return ret

        self._csv_map = csv_map()
        self._overrides, self._overriddens, self._parents, self._children = condense_global(self._temp_folder,
                            chain.from_iterable(self._csv_map.itervalues()))

    def file_to_index(self, path, contents):
        return FileToIndex(path,
                           contents,
                           self.plugin_name,
                           self.tree,
                           self._overrides,
                           self._overriddens,
                           self._parents,
                           self._children,
                           self._csv_map[sha1(path).hexdigest()],
                           self._temp_folder)
