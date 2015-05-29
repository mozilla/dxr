"""DXR plugin for Rust. Relies on output from running rustc with -Zsave-analysis

It is somewhat painful dealing with the untyped-ness of the CSV input. We want
to treat all ids as ints rather than strings, getting this wrong causes annoying
bugs because Python will not check the type of things, but does distinguish between
`n: int` and `'n': string`, and thus dictionary lookups will mysteriously fail.

* All input is strings
* Anything placed into the hashtable data must have had all ids converted to ints
  - that is mostly (but not all) done by convert_ids/find_id (since we convert
    Rust NodeIds/DefIds to internal ids)
* Helper methods might take args which may or may not have been int-ified :-(

This will all go away when we convert to using JSON instead of CSV for the data
interchange format.

Line and column numbers are stored as strings though.

"""
import csv
import os
import sys
from operator import itemgetter
from itertools import chain, izip, ifilter
from functools import partial

from jinja2 import Markup
from funcy import (merge, imap, group_by, is_mapping, repeat, compose,
                   constantly, icat)

from dxr import indexers
from dxr.plugins import Plugin, filters_from_namespace
import dxr.utils as utils
from dxr.filters import LINE
from dxr.indexers import Extent, Position, iterable_per_line, with_start_and_end, split_into_lines, QUALIFIED_LINE_NEEDLE

from dxr.plugins.rust import filters
import dxr.plugins.rust.menu

PLUGIN_NAME = 'rust'
RUST_DXR_FLAG = " -Zsave-analysis"

# We know these crates come from the rust distribution (probably, the user could
# override that, but lets assume for now...).
std_libs = ['alloc', 'arena', 'backtrace', 'collections', 'core', 'coretest',
            'flate','fmt_macros', 'getopts', 'graphviz', 'libc', 'log', 'rand',
            'rbml', 'regex', 'rustc', 'rustc_bitflags', 'rustc_back', 'rustc_borrowck',
            'rustc_driver', 'rustc_llvm', 'rustc_privacy', 'rustc_resolve', 'rustc_trans',
            'rustc_typeck', 'rustdoc', 'serialize', 'std', 'syntax', 'term',
            'test', 'unicode']

id = 0
def next_id():
    global id
    id += 1
    return id

class FileToIndex(indexers.FileToIndex):
    def __init__(self, path, contents, plugin_name, tti):
        super(FileToIndex, self).__init__(path, contents, plugin_name, tti.tree)
        self.tree_index = tti

    def needles_by_line(self):
        #iterable of key/value mapping; one iterable per line
        return self.all_needles()

    def refs(self):
        def make_menu_and_title(table_name, function_name):
            data = self.tree_index.by_file(table_name, self.path)
            for datum in data:
                menu_func = getattr(menu, function_name)
                menu_and_title = menu_func(self.tree_index, datum, self.tree)
                if menu_and_title:
                    if 'extent_start' in datum:
                        yield (int(datum['extent_start']),
                               int(datum['extent_end']),
                               menu_and_title)

        for m in make_menu_and_title('functions', 'function_menu'):
            yield m
        for m in make_menu_and_title('function_refs', 'function_ref_menu'):
            yield m
        for m in make_menu_and_title('variables', 'variable_menu'):
            yield m
        for m in make_menu_and_title('variable_refs', 'variable_ref_menu'):
            yield m
        for m in make_menu_and_title('types', 'type_menu'):
            yield m
        for m in make_menu_and_title('type_refs', 'type_ref_menu'):
            yield m
        for m in make_menu_and_title('modules', 'module_menu'):
            yield m
        for m in make_menu_and_title('module_refs', 'module_ref_menu'):
            yield m
        for m in make_menu_and_title('module_aliases', 'module_alias_menu'):
            yield m
        for m in make_menu_and_title('unknown_refs', 'unknown_ref_menu'):
            yield m

        # Note there is no ref for impls since both the trait and struct parts
        # are covered as refs already. If you add this, then you will get overlapping
        # extents, which is bad. We have impl_defs in the db because we do want
        # to jump _to_ them.


    def annotations_by_line(self):
        # FIXME(#4) links in the lefthand margin (warnings, etc.)
        return []

    def links(self):
        # FIXME(#16) RHS links
        #return (sort order, heading, [(icon, title, href), ...])
        return []

    def all_needles(self):
        return iterable_per_line(with_start_and_end(split_into_lines(chain(
            self.file_needles('function', 'functions'),
            self.file_needles('function_ref', 'function_refs'),
            self.file_needles('var', 'variables'),
            self.file_needles('var_ref', 'variable_refs'),
            self.file_needles('type', 'types'),
            self.file_needles('type_ref', 'type_refs'),
            self.file_needles('module', 'modules'),
            self.file_needles('module_ref', 'module_refs'),
            self.file_needles('module_alias_ref', 'module_aliases'),
            self.alias_needles(),
            self.module_use_needles(),
            self.file_needles('extern_ref', 'unknown_refs'),
            self.impl_needles(),
            self.fn_impls_needles(),
            self.inherit_needles(self.tree_index.super_traits, 'derived'),
            self.inherit_needles(self.tree_index.sub_traits, 'bases'),
            self.call_needles(self.tree_index.callers, 'called_by'),
            self.call_needles(self.tree_index.callees, 'callers'),
        ))))

    def file_needles(self, filter_name, table_name, keys=('name', 'qualname')):
        data = self.tree_index.by_file(table_name, self.path)
        return self.needles_for_table(filter_name, data)

    def needles_for_table(self ,filter_name, data):
        # Each needle is a (needle name, needle value dict, Extent) triple.
        result = (('rust_{0}'.format(filter_name),
                 datum,
                 self.make_span(datum))
                for datum in data if 'extent_start' in datum)
        return result

    def alias_needles(self):
        # When we have a reference to an alias, it is useful to have a needle for
        # both the alias and the aliased 'module'.
        refs = self.tree_index.by_file('module_refs', self.path)
        aliases = self.tree_index.data.module_aliases
        mods = self.tree_index.data.modules
        for datum in refs:
            if datum['aliasid'] in aliases:
                a_ref = aliases[datum['aliasid']]
                alias = {
                    'qualname': a_ref['qualname'],
                    'name': a_ref['name']
                }
                yield ('rust_module_alias_ref', alias, self.make_span(datum))
                if a_ref['refid'] in mods:
                    mod = {
                        'qualname': mods[a_ref['refid']]['qualname'],
                        'name': mods[a_ref['refid']]['name']
                    }
                    yield ('rust_module_ref', mod, self.make_span(datum))


    def module_use_needles(self):
        aliases = self.tree_index.by_file('module_aliases', self.path)
        modules = self.tree_index.data.modules
        for datum in aliases:
            if datum['refid'] in modules:
                alias = {
                    'qualname': modules[datum['refid']]['qualname'],
                    'name': modules[datum['refid']]['name']
                }
                yield ('rust_module_use', alias, self.make_span(datum))

    def impl_needles(self):
        impls = self.tree_index.by_file('impl_defs', self.path)
        types = self.tree_index.data.types
        for datum in impls:
            if datum['refid'] in types:
                impl = {
                    'qualname': types[datum['refid']]['qualname'],
                    'name': types[datum['refid']]['name']
                }
                yield ('rust_impl', impl, self.make_span(datum))
            if datum['traitid'] in types:
                impl = {
                    'qualname': types[datum['traitid']]['qualname'],
                    'name': types[datum['traitid']]['name']
                }
                yield ('rust_impl', impl, self.make_span(datum))

    def fn_impls_needles(self):
        fns = self.tree_index.by_file('functions', self.path)
        all_fns = self.tree_index.data.functions
        for datum in fns:
            if 'declid' in datum and datum['declid'] in all_fns:
                fn = {
                    'qualname': all_fns[datum['declid']]['qualname'],
                    'name': all_fns[datum['declid']]['name']
                }
                yield ('rust_fn_impls', fn, self.make_span(datum))

    def inherit_needles(self, inheritance, filter_name):
        types = self.tree_index.by_file('types', self.path)
        all_types = self.tree_index.data.types
        for datum in types:
            if datum['id'] not in inheritance:
                continue
            for s in inheritance[datum['id']]:
                t = {
                    'qualname': all_types[s]['qualname'],
                    'name': all_types[s]['name']
                }
                yield ('rust_{0}'.format(filter_name), t, self.make_span(datum))

    def call_needles(self, calls, filter_name):
        fns = self.tree_index.by_file('functions', self.path)
        all_fns = self.tree_index.data.functions
        for datum in fns:
            if datum['id'] not in calls:
                continue
            for s in calls[datum['id']]:
                fn = {
                    'qualname': all_fns[s]['qualname'],
                    'name': all_fns[s]['name']
                }
                yield ('rust_{0}'.format(filter_name), fn, self.make_span(datum))


    # Takes a row of data and returns an Extent.
    def make_span(self, row):
        return Extent(Position(int(row['file_line']), int(row['file_col'])),
                      Position(int(row['file_line_end']), int(row['file_col_end'])))


class RustLine:
    def __init__(self):
        self.defs = []


class RustFile:
    def __init__(self):
        self.lines = {}

    def get_line(self, line):
        if line not in self.lines:
            self.lines[line] = RustLine()

        return self.lines[line]

# Data for the tree, mappings for each of the various kinds of language item to
# the place it occurs and info about it. 
class TreeData:
    def __init__(self):
        # non-refs are id->args, refs are lists
        self.unknowns = {}
        self.unknown_refs = []
        self.modules = {}
        # A module for each crate linked using extern crate, indexed by the module id for the crate
        self.extern_crate_mods = {}
        self.module_refs = []
        self.module_aliases = {}
        self.variables = {}
        self.variable_refs = []
        self.functions = {}
        self.function_refs = []
        self.types = {}
        self.type_refs = []
        self.impl_defs = {}

        self.indices = {}

    # Create an index for a dict
    def index(self, table_name, field_name):
        if (table_name, field_name) in self.indices:
            return self.indices[(table_name, field_name)]

        table = getattr(self, table_name)
        index = {}
        values = None
        if table_name.endswith('_refs'):
            values = table
        else:
            values = table.values()
        for v in values:
            if field_name in v and v[field_name]:
                if v[field_name] in index:
                    index[v[field_name]].append(v)
                else:
                    index[v[field_name]] = [v]
        self.indices[(table_name, field_name)] = index
        return index

    def delete_indices(self):
        self.indices = {}


class TreeToIndex(indexers.TreeToIndex):
    def __init__(self, plugin_name, tree, vcs_cache):
        super(TreeToIndex, self).__init__(plugin_name, tree, vcs_cache)
        self.tree = tree

        src_folder = self.tree.source_folder
        if not src_folder.endswith('/'):
            src_folder += '/'
        self.src_folder = src_folder
        self.crate_map = {}
        self.crates_by_name = {}
        self.id_map = {}
        self.local_libs = []
        self.files = {} # map from file name to RustFile, which in turn stores all data
                        # mapping location -> info.
        self.data = TreeData()
        # Map from the id of a scope to the id of its parent (or 0), if there is no parent.
        # Note that these are Rust ids, not DXR ids
        self.mod_parents = {}
        # map from ctor_id to def_id for structs
        # The domains should be disjoint
        self.ctor_ids = {}
        # list of (base, derived) trait ids
        self.inheritance = []
        # convenience lookups for self.inheritance
        self.sub_traits = {}
        self.super_traits = {}
        # maps from a fn to its callers or callees (by id)
        self.callers = {}
        self.callees = {}
        # map from inner to outer scopes
        self.scope_inheritance = {}
        # URLs for std libs
        self.locations = {}
        # The name of the crate being processed
        self.crate_name = None

        self._temp_folder = os.path.join(self.tree.temp_folder, 'plugins', PLUGIN_NAME)


    # return data by file, indexed by the file's path
    def by_file(self, table_name, file_path):
        table = self.data.index(table_name, 'file_name')

        if file_path not in table:
            return []

        return table[file_path]

    def environment(self, env):
        print("rust-dxr environment")
        # Setup environment variables for using the rust-dxr tool
        # We'll store all the havested metadata in the plugins temporary folder.

        env['RUSTC'] = env.get('RUSTC', 'rustc') + RUST_DXR_FLAG
        if 'RUSTFLAGS_STAGE2' in env:
            env['RUSTFLAGS_STAGE2'] += RUST_DXR_FLAG
        else:
            env['RUSTFLAGS_STAGE2'] = RUST_DXR_FLAG
        env['DXR_RUST_OBJECT_FOLDER'] = self.tree.object_folder
        env['DXR_RUST_TEMP_FOLDER'] = self._temp_folder

        return env


    def post_build(self):
        print "rust-dxr post_build"
        for root, dirs, files in os.walk(self._temp_folder):
            print " - Processing files - first pass"
            for f in [f for f in files if f.endswith('.csv')]:
                self.process_csv_first_pass(os.path.join(root, f))
                self.crate_name = None
            print " - Processing files - second pass"
            for f in [f for f in files if f.endswith('.csv')]:
                self.process_csv_second_pass(os.path.join(root, f))
                self.crate_name = None

            # don't need to look in sub-directories
            break

        print " - Updating references"
        self.fixup_struct_ids()
        self.fixup_sub_mods()

        print " - Generating inheritance graph"
        self.generate_inheritance()
        self.generate_callgraph()

        print " - Generating crate info"
        self.generate_locations()

        print " - Generating qualnames"
        self.generate_qualnames()


    def file_to_index(self, path, contents):
        return FileToIndex(path, contents, self.plugin_name, self)


    # Just record the crates we index (process_crate).
    def process_csv_first_pass(self, path):
        self.process_csv(path, True)

    # All the proper indexing.
    def process_csv_second_pass(self, path):
        self.process_csv(path, False)

        # We need to do this once per crate whilst the current crate is still current
        self.generate_scopes()
        self.std_hack()

    def process_csv(self, file_name, header_only):
        try:
            f = open(file_name, 'rb')
            print 'processing ' + file_name
            parsed_iter = csv.reader(f)

            try:
                # the first item on a line is the kind of entity we are dealing with and so
                # we can use that to dispatch to the appropriate process_... function
                for line in parsed_iter:

                    # convert key:value pairs to a map
                    args = {}
                    for i in range(1, len(line), 2):
                        args[line[i]] = line[i + 1]

                    func = None
                    try:
                        func = globals()['process_' + line[0]]
                    except KeyError:
                        print " - 'process_" + line[0] + "' not implemented!"
                        continue

                    if 'file_name' in args and args['file_name'].startswith(self.tree.source_folder):
                        args['file_name'] = args['file_name'][len(self.tree.source_folder)+1:]

                    stop = func(args, self)
                    if stop and header_only:
                        break

            except Exception:
                print "error in", file_name, line
                raise
        except Exception:
            print "error in", file_name
            raise
        finally:
            f.close()

    def fixup_struct_ids(self):
        """ Sadness. Structs have an id for their definition and an id for their ctor.
            Sometimes, we get one, sometimes the other. This method fixes up any refs
            to the latter into refs to the former."""

        type_refs_by_ref = self.data.index('type_refs', 'refid')
        for ctor in self.ctor_ids.keys():
            if ctor in type_refs_by_ref:
                for ref in type_refs_by_ref[ctor]:
                    ref['refid'] = self.ctor_ids[ctor]
        # Indices are now out of date, need to delete them
        self.data.delete_indices()


    def fixup_sub_mods(self):
        """ When we have a path like a::b::c, we want to have info for a and a::b.
            Unfortunately Rust does not give us much info, so we have to
            construct it ourselves from the module info we have.
            We have the qualname for the module (e.g, a or a::b) but we do not have
            the refid. """
        self.fixup_sub_mods_impl('modules', 'module_refs')
        # paths leading up to a static method have a module path, then a type at the end,
        # so we have to fixup the type in the same way as we do modules.
        self.fixup_sub_mods_impl('types', 'type_refs')
        # Some module_refs are refs to types, e.g., enums in paths
        self.fixup_sub_mods_impl('types', 'module_refs')


    # FIXME - does not seem to work for external crates - refid = 0, crateid = 0
    # they must be in the same module crate as their parent though, and we can cache
    # module name and scope -> crate and always get a hit, so maybe we can win.
    def fixup_sub_mods_impl(self, table_name, table_ref_name):
        """ NOTE table_name and table_ref_name should not come from user input, otherwise
            there is potential for SQL injection attacks. """
        # First create refids for module refs whose qualnames match the qualname of
        # the module (i.e., no aliases).
        table_refs = getattr(self.data, table_ref_name)
        table_by_name = self.data.index(table_name, 'qualname')
        for v in table_refs:
            if v['refid'] > 0:
                continue
            if v['qualname'] and v['qualname'] in table_by_name:
                v['refid'] = table_by_name[v['qualname']][0]['id']



        # We do our own scpoing of aliases and it is kinda nasty. We keep a record
        # of a reflexive, transitive 'inside' relation for scopes in impl. So we
        # check that the alias is outside the reference to the alias.
        # XXX This does not take into account overriding/shadowing, so if there is
        # an alias in a smaller scope which hides an outer alias, it is chance which
        # you will get.
        if table_name == 'modules':
            # Next account for where the path is an aliased modules e.g., alias::c,
            # where c is already accounted for.
            module_aliases_by_scope = self.data.index('module_aliases', 'scopeid')

            module_refs_0 = [item for item in self.data.module_refs if item['refid'] == -1]
            for mod_ref in module_refs_0:
                if mod_ref['scopeid'] not in self.scope_inheritance:
                    continue
                parent_ids = self.scope_inheritance[mod_ref['scopeid']]
                for parent_id in parent_ids:
                    if parent_id in module_aliases_by_scope:
                        for alias in module_aliases_by_scope[parent_id]:
                            if alias['name'] == mod_ref['qualname']:
                                qualname = str(parent_id) +"$" + alias['name']
                                mod_ref['qualname'] = qualname

                                mod = None
                                id = alias['refid']
                                if id in self.data.modules:
                                    mod = self.data.modules[id]
                                elif id in self.data.extern_crate_mods:
                                    mod = self.data.extern_crate_mods[id]
                                if mod:
                                    mod_ref['refid'] = mod['id']
                                    mod_ref['aliasid'] = alias['id']


    def generate_inheritance(self):
        direct = [(base, derived) for (base, derived) in self.inheritance]
        transitive = [(base, derived) for (base, derived) in self.closure(self.inheritance) if (base, derived) not in self.inheritance]
        self.inheritance = direct + transitive
        for (b, d) in self.inheritance:
            self.sub_traits.setdefault(b, []).append(d)
            self.super_traits.setdefault(d, []).append(b)


    def generate_callgraph(self):
        # staticaly dispatched call
        static_calls = [(value['refid'], value['scopeid']) for value in self.data.function_refs if value['refid'] and value['refid'] in self.data.functions and value['scopeid'] in self.data.functions]

        # dynamically dispatched call
        fns_by_declid = self.data.index('functions', 'declid')
        dynamic_calls = [(fns_by_declid[value['declid']][0]['id'], value['scopeid'])
                            for value in self.data.function_refs
                            if ('refid' not in value or not value['refid']) and 'declid' in value and value['declid'] in fns_by_declid and fns_by_declid[value['declid']][0]['id'] in self.data.functions and value['scopeid'] in self.data.functions]

        for (er, ee) in static_calls + dynamic_calls:
            self.callers.setdefault(er, []).append(ee)
            self.callees.setdefault(ee, []).append(er)


    def generate_locations(self):
        docurl = "http://static.rust-lang.org/doc/master/%s/index.html"
        srcurl = "https://github.com/rust-lang/rust/tree/master/src/lib%s"
        dxrurl = "http://dxr.mozilla.org/rust/source/lib%s/lib.rs.html"
        for l in std_libs:
            # If we are indexing the standard libs for some reason, then don't give
            # them special treatment.
            if l not in self.local_libs:
                self.locations[l] = (docurl%l, srcurl%l, dxrurl%l)


    def generate_qualnames(self):
        def generate_qualname_for_table(ref_table, table):
            for datum in ref_table:
                if 'qualname' not in datum or not datum['qualname']:
                    if datum['refid'] and datum['refid'] in table:
                        datum['qualname'] = table[datum['refid']]['qualname']
                        datum['name'] = table[datum['refid']]['name']

        generate_qualname_for_table(self.data.type_refs, self.data.types)
        generate_qualname_for_table(self.data.module_refs, self.data.types)
        generate_qualname_for_table(self.data.variable_refs, self.data.variables)

        # function refs
        for f in self.data.function_refs:
            if 'qualname' not in f or not f['qualname']:
                if 'refid' in f and f['refid'] and f['refid'] in self.data.functions:
                    fn_def = self.data.functions[f['refid']]
                    f['qualname'] = fn_def['qualname']
                    f['name'] = fn_def['name']
                elif 'refid' in f and f['refid'] and f['refid'] in self.data.types:
                    fn_def = self.data.types[f['refid']]
                    f['qualname'] = fn_def['qualname']
                    f['name'] = fn_def['name']
                elif 'declid' in f and f['declid'] and f['declid'] in self.data.functions:
                    fn_decl = self.data.functions[f['declid']]
                    f['qualname'] = fn_decl['qualname']
                    f['name'] = fn_decl['name']

        # unknown refs
        for datum in self.data.unknown_refs:
            if 'qualname' not in datum or not datum['qualname']:
                if datum['refid']:
                    datum['qualname'] = datum['refid']
                    datum['name'] = datum['refid']

        # module aliases
        for datum in self.data.module_refs:
            if 'qualname' not in datum or not datum['qualname']:
                if datum['aliasid'] and datum['aliasid'] in self.data.module_aliases:
                    alias = self.data.module_aliases[datum['aliasid']]
                    datum['qualname'] = alias['qualname']
                    datum['name'] = alias['name']





    def generate_scopes(self):
        self.scope_inheritance[self.find_id_cur(0)] = [self.find_id_cur(0)]
        for (child, parent) in self.mod_parents.items():
            self.scope_inheritance.setdefault(child, []).append(parent)
            # reflexivity
            self.scope_inheritance.setdefault(child, []).append(child)

        # transitivity
        for (child, parent) in self.closure(self.mod_parents.items()):
            if (child, parent) not in self.mod_parents.items():
                self.scope_inheritance.setdefault(child, []).append(parent)

        self.mod_parents = {}

    def std_hack(self):
        # This is nasty - Rust implicitly includes the standard library,
        # crate `std`, but without generating an `extern crate` item, so we need
        # to do that. However, it is possible the project includes some other crate
        # called `std` (by building without the standard lib, we can't tell from 
        # the indexing data which is the case), so we need to check in case there
        # is one already.
        # We probably wouldn't need this if we dealt with generated code properly
        # in the compiler indexing.
        if 'std' not in self.data.index('module_aliases', 'name').keys():
            id = next_id()
            scopeid = self.find_id_cur('0')
            args = {
                'name': 'std',
                'location': 'std',
                'id': id,
                'scopeid': scopeid,
                # Jesus, this is fragile
                'crate': '1',
                'qualname': str(scopeid) + '$std',
                'refid': self.crate_map[1][1]['id']
            }
            self.data.module_aliases[id] = args


    def closure(self, input):
        """ Compute the (non-refexive) transitive closure of a list."""

        closure = set(input)
        while True:
            next_set = set([(b,dd) for (b,d) in closure for (bb,dd) in closure if d == bb])
            next_set |= closure

            if next_set == closure:
                return closure

            closure = next_set


    def find_id(self, crate, node):
        """ Maps a crate name and a node number to a globally unique id. """
        if node == None:
            return None

        if node < 0:
            return node

        node = int(node)

        if (crate, node) not in self.id_map:
            result = next_id()
            self.id_map[(crate, node)] = (result, 0)
            return result

        return self.id_map[(crate, node)][0]


    def add_external_item(self, args):
        """ Returns True if the refid in the args points to an item in an external crate. """
        node, crate = args['refid'], args['refidcrate']
        if not node:
            return False
        crate = self.crate_map[int(crate)][0]
        if crate in self.local_libs:
            return False

        id = self.find_id(crate, node)
        if id not in self.data.unknowns:
            self.data.unknowns[id] = {'id': id, 'crate': crate }

        args = self.convert_ids(args)
        self.data.unknown_refs.append(args)
        self.add_to_lines(args, ('unknowns', args))

        return True


    def add_external_decl(self, args):
        decl_node, decl_crate = args['declid'], args['declidcrate']
        if not decl_node:
            return False
        decl_crate = self.crate_map[int(decl_crate)][0]
        if decl_crate in self.local_libs:
            return False

        id = self.find_id(decl_crate, decl_node)
        if id not in self.data.unknowns:
            self.data.unknowns[id] = {'id': id, 'crate': decl_crate }

        new_args = self.convert_ids(args)
        new_args['refid'] = new_args['declid']
        self.add_to_lines(new_args, ('unknowns', new_args))

        args['refid'] = new_args['declid']
        return True


    def add_to_lines(self, args, data):
        r_file = self.get_file(args['file_name'])
        start_line = args['file_line']
        end_line = args['file_line_end']
        for i in range(int(start_line), int(end_line) + 1):
            r_line = r_file.get_line(i)
            r_line.defs.append(data)

    def get_file(self, file_name):
        if file_name.startswith(self.src_folder):
            file_name = file_name[len(self.src_folder):]

        if file_name in self.files:
            return self.files[file_name]

        r_file = RustFile()
        self.files[file_name] = r_file
        return r_file


    # XXX this feels a little bit fragile...
    def convert_ids(self, args):
        def convert(k, v):
            if k.endswith('crate'):
                return -1
            elif k == 'ctor_id' or k == 'aliasid':
                return int(v)
            elif k == 'refid' and (not v or int(v) <= 0):
                return -1
            elif k == 'id' or k == 'scopeid':
                return self.find_id_cur(v)
            elif v == '' and (k.endswith('id') or k == 'base' or k == 'derived'):
                return None
            elif k.endswith('id') or k == 'base' or k == 'derived':
                return self.find_id(self.crate_map[int(args[k + 'crate'])][0], v)
            else:
                return v

        new_args = {k: convert(k, v) for k, v in args.items() if not k.endswith('crate')}
        return new_args


    def find_id_cur(self, node):
        """ Shorthand for nodes in the current crate. """
        return self.find_id(self.crate_map[0][0], node)

    def fixup_qualname(self, datum):
        # FIXME(#19) we should not do this here, we should do it in the compiler
        if 'qualname' in datum and datum['qualname'] and datum['qualname'][:2] == '::':
            datum['qualname'] = self.crate_name + datum['qualname']


# FIXME(#15) all these process_* methods would be better off in TreeToIndex

def process_crate(args, tree):
    """ There should only be one of these per crate and it gives info about the current
        crate.
        Note that this gets called twice for the same crate line - once per pass. """

    if args['name'] not in tree.local_libs:
        tree.local_libs.append(args['name'])
    args = tree.convert_ids(args)
    args['id'] = next_id()
    tree.crate_map[0] = (args['name'], args)
    tree.crates_by_name[args['name']] = args
    tree.crate_name = args['name']


def process_external_crate(args, tree):
    """ These have to happen before anything else in the csv and have to be concluded
        by 'end_external_crate'. """

    mod_id = next_id()
    name = args['name']
    id = int(args['crate'])
    args = {'id': mod_id,
            'name': name,
            'qualname': "0$" + name,
            'def_file': args['file_name'],
            'kind': 'extern',
            'scopeid': 0,
            'extent_start': -1,
            'extent_end': -1}
    # don't need to convert_args because the args are all post-transform

    tree.data.extern_crate_mods[mod_id] = args

    tree.crate_map[id] = (name, args)


def process_type_ref(args, tree):
    if tree.add_external_item(args):
        return;

    args = tree.convert_ids(args)
    tree.fixup_qualname(args)

    if 'qualname' not in args:
        args['qualname'] = ''

    tree.data.type_refs.append(args)
    tree.add_to_lines(args, ('type_refs', args))


def process_variable(args, tree):
    args = tree.convert_ids(args)
    tree.fixup_qualname(args)
    tree.data.variables[args['id']] = args
    tree.add_to_lines(args, ('variables', args))


def process_function_impl(args, tree):
    args['name'] = args['qualname'].split('::')[-1]
    args['args'] = ''
    args['type'] = ''
    args = tree.convert_ids(args)
    tree.fixup_qualname(args)

    tree.mod_parents[int(args['id'])] = int(args['scopeid'])
    tree.data.functions[args['id']] = args
    tree.add_to_lines(args, ('functions', args))


def process_function(args, tree):
    process_function_impl(args, tree)


def process_method_decl(args, tree):
    process_function_impl(args, tree)


def process_enum(args, tree):
    args['kind'] = 'enum'
    args['name'] = args['qualname'].split('::')[-1]
    args = tree.convert_ids(args)
    tree.fixup_qualname(args)

    tree.data.types[args['id']] = args
    tree.add_to_lines(args, ('types', args))


def process_struct(args, tree, kind = 'struct'):
    # Used for fixing up the refid in fixup_struct_ids
    if args['ctor_id'] != '-1':
        tree.ctor_ids[tree.find_id_cur(args['ctor_id'])] = tree.find_id_cur(args['id'])

    args['name'] = args['qualname'].split('::')[-1]
    tree.fixup_qualname(args)
    args['kind'] = kind

    scope_args = tree.convert_ids({'id': args['id'],
                                   'name' : args['name']})

    args = tree.convert_ids(args)
    tree.mod_parents[int(args['id'])] = int(args['scopeid'])
    tree.data.types[args['id']] = args
    tree.add_to_lines(args, ('types', args))


def process_impl(args, tree):
    scope_args = tree.convert_ids({'id': args['id'],
                                   'name' : 'impl'})
    args = tree.convert_ids(args)
    tree.fixup_qualname(args)
    tree.mod_parents[int(args['id'])] = int(args['scopeid'])
    tree.data.impl_defs[args['id']] = args
    tree.add_to_lines(args, ('impl_defs', args))


def process_fn_call(args, tree):
    if tree.add_external_item(args):
        return;

    args = tree.convert_ids(args)
    tree.fixup_qualname(args)
    tree.data.function_refs.append(args)
    tree.add_to_lines(args, ('function_refs', args))


def process_var_ref(args, tree):
    if tree.add_external_item(args):
        return;

    args = tree.convert_ids(args)
    tree.fixup_qualname(args)
    tree.data.variable_refs.append(args)
    tree.add_to_lines(args, ('variable_refs', args))


def process_struct_ref(args, tree):
    if 'qualname' not in args:
        args['qualname'] = ''
    process_type_ref(args, tree)


def process_method_call(args, tree):
    if args['refid'] == '0':
        args['refid'] = None

    ex_def = tree.add_external_item(args)
    ex_decl = tree.add_external_decl(args)
    if ex_def and ex_decl:
        return;
    if (ex_def and not args['declid']) or (ex_decl and not args['refid']):
        # FIXME, I think this is meant to be an assertion, but not sure
        print "Unexpected(?) missing id in method call"
        return;

    args = tree.convert_ids(args)
    tree.fixup_qualname(args)
    tree.data.function_refs.append(args)
    tree.add_to_lines(args, ('function_refs', args))


def process_mod_ref(args, tree):
    args['name'] = args['qualname'].split('::')[-1]

    if tree.add_external_item(args):
        return;
    args['aliasid'] = 0

    args = tree.convert_ids(args)
    tree.fixup_qualname(args)
    tree.data.module_refs.append(args)
    tree.add_to_lines(args, ('module_refs', args))


def process_use_alias(args, tree):
    # module_aliases includes aliases to things other than modules
    args = tree.convert_ids(args)
    args['qualname'] = str(args['scopeid']) + "$" + args['name']
    tree.data.module_aliases[args['id']] = args
    tree.add_to_lines(args, ('module_aliases', args))


def process_typedef(args, tree):
    args['name'] = args['qualname'].split('::')[-1]
    args['kind'] = 'typedef'

    args = tree.convert_ids(args)
    tree.fixup_qualname(args)
    tree.data.types[args['id']] = args
    tree.add_to_lines(args, ('types', args))

def process_variant(args, tree):
    process_variable(args, tree)

def process_variant_struct(args, tree):
    process_struct(args, tree, 'variant_struct')

def process_trait(args, tree):

    args['name'] = args['qualname'].split('::')[-1]
    args['kind'] = 'trait'

    scope_args = tree.convert_ids({'id': args['id'],
                                   'name' : 'name'})

    args = tree.convert_ids(args)
    tree.fixup_qualname(args)
    tree.mod_parents[int(args['id'])] = int(args['scopeid'])
    tree.data.types[args['id']] = args
    tree.add_to_lines(args, ('types', args))


def process_module(args, tree):
    args['name'] = args['qualname'].split('::')[-1]
    # Need the file name for the menu, at least
    # args['def_file'] = tree.get_file(args['def_file'])
    args['kind'] = 'mod'

    scope_args = tree.convert_ids({'id': args['id'],
                                   'name' : 'name'})

    args = tree.convert_ids(args)
    tree.fixup_qualname(args)
    tree.mod_parents[int(args['id'])] = int(args['scopeid'])
    tree.data.modules[args['id']] = args
    tree.add_to_lines(args, ('modules', args))


# FIXME: hmm, I'm not exactly clear on the difference between a fn call and fn ref, some of the former
# are logically the latter and this is stupid code dup...
def process_fn_ref(args, tree):
    if tree.add_external_item(args):
        return;

    args = tree.convert_ids(args)
    tree.fixup_qualname(args)
    tree.data.function_refs.append(args)
    tree.add_to_lines(args, ('function_refs', args))


def process_extern_crate(args, tree):
    crate = int(args['crate'])
    args['refid'] = '0'
    args['refidcrate'] = '0'
    
    args = tree.convert_ids(args)
    args['qualname'] = str(args['scopeid']) + "$" + args['name']   
    args['refid'] = tree.crate_map[crate][1]['id']

    tree.data.module_aliases[args['id']] = args
    tree.add_to_lines(args, ('module_aliases', args))


def process_inheritance(args, tree):
    args = tree.convert_ids(args)
    tree.inheritance.append((args['base'], args['derived']))

def process_use_glob(args, tree):
    # FIXME(#9)
    pass

def process_end_external_crates(args, tree):
    # We've got all the info we're going to get about external crates now.
    return True


mappings = {
    LINE: {
        'properties': {
            'rust_function': QUALIFIED_LINE_NEEDLE,
            'rust_function_ref': QUALIFIED_LINE_NEEDLE,
            'rust_var': QUALIFIED_LINE_NEEDLE,
            'rust_var_ref': QUALIFIED_LINE_NEEDLE,
            'rust_type': QUALIFIED_LINE_NEEDLE,
            'rust_type_ref': QUALIFIED_LINE_NEEDLE,
            'rust_module': QUALIFIED_LINE_NEEDLE,
            'rust_module_ref': QUALIFIED_LINE_NEEDLE,
            'rust_module_alias_ref': QUALIFIED_LINE_NEEDLE,
            'rust_extern_ref': QUALIFIED_LINE_NEEDLE,
            'rust_module_use': QUALIFIED_LINE_NEEDLE,
            'rust_impl': QUALIFIED_LINE_NEEDLE,
            'rust_fn_impls': QUALIFIED_LINE_NEEDLE,
            'rust_bases': QUALIFIED_LINE_NEEDLE,
            'rust_derived': QUALIFIED_LINE_NEEDLE,
            'rust_callers': QUALIFIED_LINE_NEEDLE,
            'rust_called_by': QUALIFIED_LINE_NEEDLE,
        }
    }
}

plugin = Plugin(filters=filters_from_namespace(filters.__dict__),
                tree_to_index=TreeToIndex,
                mappings=mappings)
