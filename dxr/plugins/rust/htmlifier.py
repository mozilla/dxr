import os
import fnmatch
import dxr.plugins
from dxr.utils import search_url

_tree = None
_conn = None

def load(tree, conn):
    global _tree, _conn
    _tree = tree
    _conn = conn

class RustHtmlifier(object):
    def __init__(self, tree, conn, path, text, file_id):
        self.tree    = tree
        self.conn    = conn
        self.path    = path
        self.text    = text
        self.file_id = file_id

    def regions(self):
        return []

    def refs(self):
        """ Generate reference menus """
        # We'll need this argument for all queries here
        args = (self.file_id,)

        # Note there is no ref for impls since both the trait and struct parts
        # are covered as refs already. If you add this, then you will get overlapping
        # extents, which is bad. We have impl_defs in the db because we do want
        # to jump _to_ them.

        # Extents for functions definitions
        sql = """
            SELECT extent_start, extent_end, qualname, id, declid
                FROM functions
              WHERE file_id = ?
        """
        for start, end, qualname, def_id, declid, in self.conn.execute(sql, args):
            if declid:
                # XXX I'm sure someone with more SQL smarts than me could do this
                # in one statement
                sql = """
                    SELECT (SELECT path FROM files WHERE files.id = file_id),
                           file_line
                        FROM functions
                      WHERE id = ?
                """
                declpath, declline = self.conn.execute(sql, (declid, )).fetchone()
                yield start, end, (self.function_menu(qualname, def_id, declpath, declline), qualname, None)
            else:
                yield start, end, (self.function_menu(qualname, def_id), qualname, None)

        # Add references to function def only
        # These are statically dispatched functions with no trait decl.
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                          functions.qualname,
                          (SELECT path FROM files WHERE files.id = functions.file_id),
                          functions.file_line
                FROM functions, function_refs AS refs
              WHERE functions.id = refs.refid AND refs.file_id = ? AND
              refs.declid IS NULL
        """
        for start, end, qualname, path, line in self.conn.execute(sql, args):
            menu = self.function_menu(qualname, 0)
            self.add_jump_definition(menu, path, line)
            yield start, end, (menu, qualname, None)

        # Add references to function decl only
        # dynamically dispatched functions
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                          functions.qualname,
                          (SELECT path FROM files WHERE files.id = functions.file_id),
                          functions.file_line,
                          refs.declid
                FROM functions, function_refs AS refs
              WHERE functions.id = refs.declid AND refs.file_id = ? AND
              refs.refid IS NULL
        """
        for start, end, qualname, path, line, decl_id in self.conn.execute(sql, args):
            menu = self.function_menu(qualname, decl_id)
            self.add_jump_definition(menu, path, line, "Jump to trait method")
            yield start, end, (menu, qualname, None)

        # Add references to function def and decl
        # statically dispatched, but implementing a trait method
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                          fn_def.qualname,
                          (SELECT path FROM files WHERE files.id = fn_def.file_id),
                          fn_def.file_line,
                          fn_decl.qualname,
                          (SELECT path FROM files WHERE files.id = fn_decl.file_id),
                          fn_decl.file_line
                FROM functions as fn_def, functions as fn_decl, function_refs AS refs
              WHERE fn_def.id = refs.refid AND refs.file_id = ? AND
              fn_decl.id = refs.declid
        """
        for start, end, qualname, path, line, decl_qualname, decl_path, decl_line in self.conn.execute(sql, args):
            menu = self.function_menu(qualname, 0)
            if decl_line != line or decl_path != path:
                self.add_jump_definition(menu, decl_path, decl_line, "Jump to trait method")
            self.add_jump_definition(menu, path, line)
            yield start, end, (menu, qualname, None)

        # Extents for variables defined here
        sql = """
            SELECT extent_start, extent_end, qualname, type
                FROM variables
              WHERE file_id = ?
        """
        for start, end, qualname, typ in self.conn.execute(sql, args):
            yield start, end, (self.variable_menu(qualname), qualname, self.truncate_value("", typ))

        # Add references to variables
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                          variables.qualname,
                          variables.value,
                          variables.type,
                          (SELECT path FROM files WHERE files.id = variables.file_id),
                          variables.file_line
                FROM variables, variable_refs AS refs
              WHERE variables.id = refs.refid AND refs.file_id = ?
        """
        for start, end, qualname, value, typ, path, line in self.conn.execute(sql, args):
            menu = self.variable_menu(qualname)
            self.add_jump_definition(menu, path, line)
            yield start, end, (menu, qualname, self.truncate_value(value, typ))

        # Add struct and trait defs, and typedefs
        sql = """
            SELECT extent_start, extent_end, qualname, kind
                FROM types
              WHERE file_id = ?
        """
        for start, end, qualname, kind in self.conn.execute(sql, args):
            yield start, end, (self.type_menu(qualname, kind), qualname, None)

        # Add references to types
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                          types.qualname,
                          types.kind,
                          (SELECT path FROM files WHERE files.id = types.file_id),
                          types.file_line,
                          types.value
                FROM types, type_refs AS refs
              WHERE types.id = refs.refid AND refs.file_id = ?
        """
        for start, end, qualname, kind, path, line, value in self.conn.execute(sql, args):
            menu = self.type_menu(qualname, kind)
            self.add_jump_definition(menu, path, line)
            yield start, end, (menu, qualname, self.truncate_value(value))

        # modules
        sql = """
            SELECT extent_start, extent_end, qualname,
                (SELECT path FROM files WHERE files.id = modules.def_file),
                modules.def_file, modules.file_id
            FROM modules
            WHERE file_id = ? AND extent_start > 0
        """
        for start, end, qualname, mod_path, def_file_id, cur_file_id in self.conn.execute(sql, args):
            menu = self.module_menu(qualname)
            if def_file_id != cur_file_id:
                self.add_jump_definition(menu, mod_path, 1, "Jump to module defintion")
            yield start, end, (menu, qualname, None)

        # Add references to modules
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                         modules.qualname,
                        (SELECT path FROM files WHERE files.id = modules.file_id),
                        modules.file_line,
                        (SELECT path FROM files WHERE files.id = modules.def_file),
                        modules.def_file, modules.file_id
                FROM modules, module_refs AS refs
              WHERE modules.id = refs.refid AND
                refs.file_id = ? AND
                refs.aliasid = 0  AND
                modules.extent_start > 0
        """
        for start, end, qualname, path, line, mod_path, def_file_id, cur_file_id in self.conn.execute(sql, args):
            menu = self.module_menu(qualname)
            if def_file_id == cur_file_id:
                self.add_jump_definition(menu, path, line)
            else:
                self.add_jump_definition(menu, mod_path, 1, "Jump to module defintion")
                self.add_jump_definition(menu, path, line, "Jump to module declaration")
            yield start, end, (menu, qualname, None)

        # Add references to modules via aliases
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                          refs.qualname,
                          (SELECT path FROM files WHERE files.id = module_aliases.file_id),
                          module_aliases.file_line,
                          (SELECT path FROM files WHERE files.id = modules.file_id),
                          modules.file_line
                FROM modules, module_refs AS refs, module_aliases
              WHERE modules.id = refs.refid AND
                refs.file_id = ? AND
                refs.aliasid = module_aliases.id AND
                modules.extent_start > 0
        """
        for start, end, qualname, path, line, mod_path, mod_line in self.conn.execute(sql, args):
            menu = self.module_menu(qualname)
            self.add_jump_definition(menu, mod_path, mod_line, "jump to module definition")
            self.add_jump_definition(menu, path, line, "jump to alias definition")
            yield start, end, (menu, qualname, None)

        # Add module aliases. 'use' without an explicit alias and without any wildcards,
        # etc. introduces an implicit alias for the module. E.g, |use a::b::c|
        # introduces an alias |c|. In these cases, we make the alias transparent - 
        # there is no link for the alias, but we add the alias menu stuff to the
        # module ref.
        sql = """
            SELECT module_aliases.extent_start,
                module_aliases.extent_end,
                module_aliases.qualname,
                (SELECT path FROM files WHERE files.id = modules.file_id),
                modules.file_line
                FROM module_aliases, modules
              WHERE module_aliases.file_id = ? AND
                module_aliases.refid = modules.id AND
                module_aliases.name != modules.name AND
                module_aliases.location IS NULL
        """
        for start, end, qualname, mod_path, mod_line in self.conn.execute(sql, args):
            menu = self.module_alias_menu(qualname, "module-alias-ref")
            self.add_jump_definition(menu, mod_path, mod_line, "jump to module definition")
            yield start, end, (menu, qualname, None)

        # 'module' aliases to things other than modules - types, vars, fns
        sql = """
            SELECT module_aliases.extent_start,
                module_aliases.extent_end,
                types.qualname,
                (SELECT path FROM files WHERE files.id = types.file_id),
                types.file_line
                FROM module_aliases, types
              WHERE module_aliases.file_id = ? AND
                module_aliases.refid = types.id AND
                module_aliases.name != types.name AND
                module_aliases.location IS NULL
        """
        for start, end, qualname, ty_path, ty_line in self.conn.execute(sql, args):
            menu = self.module_alias_menu(qualname, "type-ref")
            self.add_jump_definition(menu, ty_path, ty_line, "jump to type definition")
            yield start, end, (menu, qualname, None)
        sql = """
            SELECT module_aliases.extent_start,
                module_aliases.extent_end,
                variables.qualname,
                (SELECT path FROM files WHERE files.id = variables.file_id),
                variables.file_line
                FROM module_aliases, variables
              WHERE module_aliases.file_id = ? AND
                module_aliases.refid = variables.id AND
                module_aliases.name != variables.name AND
                module_aliases.location IS NULL
        """
        for start, end, qualname, var_path, var_line in self.conn.execute(sql, args):
            menu = self.module_alias_menu(qualname, "var-ref")
            self.add_jump_definition(menu, var_path, var_line, "jump to variable definition")
            yield start, end, (menu, qualname, None)
        sql = """
            SELECT module_aliases.extent_start,
                module_aliases.extent_end,
                functions.qualname,
                (SELECT path FROM files WHERE files.id = functions.file_id),
                functions.file_line
                FROM module_aliases, functions
              WHERE module_aliases.file_id = ? AND
                module_aliases.refid = functions.id AND
                module_aliases.name != functions.name AND
                module_aliases.location IS NULL
        """
        for start, end, qualname, fn_path, fn_line in self.conn.execute(sql, args):
            menu = self.module_alias_menu(qualname, "function-ref")
            self.add_jump_definition(menu, fn_path, fn_line, "jump to function definition")
            yield start, end, (menu, qualname, None)

        # extern mods to known local crates
        sql = """
            SELECT module_aliases.extent_start,
                module_aliases.extent_end,
                module_aliases.qualname,
                (SELECT path FROM files WHERE files.id = crates.file_id),
                crates.file_line
            FROM module_aliases, crates
            WHERE module_aliases.file_id = ? AND
                module_aliases.location = crates.name
        """
        for start, end, qualname, mod_path, mod_line in self.conn.execute(sql, args):
            menu = self.module_alias_menu(qualname, "module-alias-ref")
            self.add_jump_definition(menu, mod_path, mod_line, "jump to crate")
            yield start, end, (menu, qualname, None)

        # extern mods to standard library crates
        sql = """
            SELECT module_aliases.extent_start,
                module_aliases.extent_end,
                module_aliases.qualname,
                extern_locations.docurl,
                extern_locations.srcurl,
                extern_locations.dxrurl
            FROM module_aliases, extern_locations
            WHERE module_aliases.file_id = ? AND
                module_aliases.location = extern_locations.location
        """
        for start, end, qualname, docurl, srcurl, dxrurl in self.conn.execute(sql, args):
            menu = self.module_alias_menu(qualname, "module-alias-ref")
            self.std_lib_links(menu, docurl, srcurl, dxrurl)
            yield start, end, (menu, qualname, None)

        # extern mods to unknown local crates
        sql = """
            SELECT module_aliases.extent_start,
                module_aliases.extent_end,
                module_aliases.qualname
            FROM module_aliases
            WHERE module_aliases.file_id = ? AND
                NOT EXISTS (SELECT 1 FROM extern_locations WHERE module_aliases.location = extern_locations.location) AND
                NOT EXISTS (SELECT 1 FROM crates WHERE module_aliases.location = crates.name) AND
                module_aliases.location IS NOT NULL
        """
        for start, end, qualname in self.conn.execute(sql, args):
            menu = self.module_alias_menu(qualname, "module-alias-ref")
            yield start, end, (menu, qualname, None)

        # Add references to extern mods via aliases (known local crates)
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                refs.qualname,
                (SELECT path FROM files WHERE files.id = module_aliases.file_id),
                module_aliases.file_line,
                (SELECT path FROM files WHERE files.id = crates.file_id),
                crates.file_line
            FROM modules, module_refs AS refs, module_aliases, crates
            WHERE modules.id = refs.refid AND
                refs.file_id = ? AND
                refs.aliasid = module_aliases.id AND
                module_aliases.location = crates.name
        """
        for start, end, qualname, path, line, mod_path, mod_line in self.conn.execute(sql, args):
            menu = self.module_alias_menu(qualname, "module-alias-ref")
            self.add_jump_definition(menu, mod_path, mod_line, "jump to crate")
            self.add_jump_definition(menu, path, line, "jump to alias definition")
            yield start, end, (menu, qualname, None)

        # Add references to extern mods via aliases (standard library crates)
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                refs.qualname,
                (SELECT path FROM files WHERE files.id = module_aliases.file_id),
                module_aliases.file_line,
                extern_locations.docurl,
                extern_locations.srcurl,
                extern_locations.dxrurl
            FROM modules, module_refs AS refs, module_aliases, extern_locations
            WHERE modules.id = refs.refid AND
                refs.file_id = ? AND
                refs.aliasid = module_aliases.id AND
                module_aliases.location = extern_locations.location
        """
        for start, end, qualname, path, line, docurl, srcurl, dxrurl in self.conn.execute(sql, args):
            menu = self.module_alias_menu(qualname, "module-alias-ref")
            self.std_lib_links(menu, docurl, srcurl, dxrurl)
            self.add_jump_definition(menu, path, line, "jump to alias definition")
            yield start, end, (menu, qualname, None)

        # Add references to extern mods via aliases (unknown local crates)
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                refs.qualname,
                (SELECT path FROM files WHERE files.id = module_aliases.file_id),
                module_aliases.file_line
            FROM modules, module_refs AS refs, module_aliases
            WHERE modules.id = refs.refid AND
                refs.file_id = ? AND
                refs.aliasid = module_aliases.id AND
                NOT EXISTS (SELECT 1 FROM extern_locations WHERE module_aliases.location = extern_locations.location) AND
                NOT EXISTS (SELECT 1 FROM crates WHERE module_aliases.location = crates.name) AND
                module_aliases.location IS NOT NULL
        """
        for start, end, qualname, path, line in self.conn.execute(sql, args):
            menu = self.module_alias_menu(qualname, "module-alias-ref")
            self.add_jump_definition(menu, path, line, "jump to alias definition")
            yield start, end, (menu, qualname, None)

        # Add references to external items (standard libraries)
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                unknowns.crate, unknowns.id,
                extern_locations.docurl,
                extern_locations.srcurl,
                extern_locations.dxrurl
            FROM unknowns, unknown_refs AS refs, extern_locations
            WHERE unknowns.id = refs.refid AND
                refs.file_id = ? AND
                unknowns.crate = extern_locations.location
        """
        for start, end, crate, uid, docurl, srcurl, dxrurl in self.conn.execute(sql, args):
            menu = self.extern_menu(uid)
            self.std_lib_links(menu, docurl, srcurl, dxrurl, " for crate")
            yield start, end, (menu, 'extern$' + str(uid), None)

        # Add references to external items
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                unknowns.crate, unknowns.id
            FROM unknowns, unknown_refs AS refs
            WHERE unknowns.id = refs.refid AND refs.file_id = ? AND
                NOT EXISTS (SELECT 1 FROM extern_locations WHERE unknowns.crate = extern_locations.location)
        """
        for start, end, crate, uid in self.conn.execute(sql, args):
            menu = self.extern_menu(uid)
            yield start, end, (menu, 'extern$' + str(uid), None)

    def truncate_value(self, value, typ=""):
        result = ""
        if value:
            eol = value.find('\n')
            if eol < 0:
                result = value.strip()
            else:
                value = value[0:eol]
                value = value.strip()
                result = value + " ..."
            result = "( " + result + " )"

        if typ:
            if result:
                result = typ + " " + result
            else:
                result = typ

        if not result:
            return None

        return result


    def search(self, query):
        """ Auxiliary function for getting the search url for query """
        return search_url(self.tree.config.wwwroot,
                          self.tree.name,
                          query)

    def quote(self, qualname):
        """ Wrap qualname in quotes if it contains spaces """
        if ' ' in qualname:
            qualname = '"' + qualname + '"'
        return qualname

    def std_lib_links(self, menu, docurl, srcurl, dxrurl, extra_text = ""):
        self.add_link_to_menu(menu, dxrurl,
                              "Go to DXR index" + extra_text,
                              "Go to DXR index of this crate on " + get_domain(dxrurl))
        self.add_link_to_menu(menu, srcurl,
                              "Go to source" + extra_text,
                              "Go to source code for this crate on " + get_domain(srcurl))
        self.add_link_to_menu(menu, docurl,
                              "Go to docs" + extra_text,
                              "Go to documentation for this crate on " + get_domain(docurl))

    def add_find_references(self, menu, qualname, search_term, kind):
        menu.append({
            'html':   "Find references",
            'title':  "Find references to this " + kind,
            'href':   self.search("+" + search_term + ":%s" % self.quote(qualname)),
            'icon':   'reference'
        })

    def function_menu(self, qualname, def_id, declpath=None, declline=None, is_trait_method=False):
        """ Build menu for a function """
        menu = []
        if declpath:
            self.add_jump_definition(menu, declpath, declline, "Jump to trait method")
        if not declpath:
            # no point adding 'find implementations' if there are no implementations
            # note, that this will include methods in structs, which have no trait
            # method or other defintions
            sql = """
                SELECT COUNT(*)
                FROM functions 
                WHERE declid = ?
            """
            c_decls = self.conn.execute(sql, (def_id,)).fetchone()[0]
            if c_decls > 0:
                menu.append({
                    'html':   "Find implementations (%d)"%c_decls,
                    'title':  "Find implementations of this trait method",
                    'href':   self.search("+fn-impls:%s" % self.quote(qualname)),
                    'icon':   'method'
                })

        menu.append({
            'html':   "Find callers",
            'title':  "Find functions that call this function",
            'href':   self.search("+callers:%s" % self.quote(qualname)),
            'icon':   'method'
        })
        menu.append({
            'html':   "Find callees",
            'title':  "Find functions that are called by this function",
            'href':   self.search("+called-by:%s" % self.quote(qualname)),
            'icon':   'method'
        })
        self.add_find_references(menu, qualname, "function-ref", "function")
        return menu

    def variable_menu(self, qualname):
        """ Build menu for a variable """
        menu = []
        self.add_find_references(menu, qualname, "var-ref", "variable")
        return menu

    def type_menu(self, qualname, kind):
        """ Build menu for type """
        menu = []
        if kind == 'trait':
            menu.append({
                'html':   "Find sub-traits",
                'title':  "Find sub-traits of this trait",
                'href':   self.search("+derived:%s" % self.quote(qualname)),
                'icon':   'type'
            })
            menu.append({
                'html':   "Find super-traits",
                'title':  "Find super-traits of this trait",
                'href':   self.search("+bases:%s" % self.quote(qualname)),
                'icon':   'type'
            })
        
        if kind == 'struct' or kind == 'trait':
            menu.append({
                'html':   "Find impls",
                'title':  "Find impls which involve this " + kind,
                'href':   self.search("+impl:%s" % self.quote(qualname)),
                'icon':   'reference'
            })
        self.add_find_references(menu, qualname, "type-ref", kind)
        return menu

    def module_menu(self, qualname):
        """ Build menu for a module """
        menu = []
        self.add_find_references(menu, qualname, "module-ref", "module")
        menu.append({
            'html':   "Find use items",
            'title':  "Find instances of this module in 'use' items",
            'href':   self.search("+module-use:%s" % self.quote(qualname)),
            'icon':   'reference'
        })
        return menu

    def module_alias_menu(self, qualname, ref_search_kind):
        """ Build menu for a module alias """
        menu = []
        self.add_find_references(menu, qualname, ref_search_kind, "alias")
        return menu

    def extern_menu(self, uid):
        """ Build menu for an external item """
        menu = []
        self.add_find_references(menu, str(uid), "extern-ref", "item")
        return menu

    def add_jump_definition(self, menu, path, line, text="Jump to definition"):
        """ Add a jump to definition to the menu """
        if not path:
            print "Can't add jump to empty path. Menu:", menu
            print "text: ", text
            return
            
        # Definition url
        url = self.tree.config.wwwroot + '/' + self.tree.name + '/source/' + path
        url += "#%s" % line
        menu.insert(0, { 
            'html':   text,
            'title':  "%s in '%s'" % (text,os.path.basename(path)),
            'href':   url,
            'icon':   'jump'
        })

    def add_link_to_menu(self, menu, url, text, long_text):
        if not url:
            return menu;

        menu.insert(0, {
            'html':   text,
            'title':  long_text,
            'href':   url,
            'icon':   'jump'
        })
        return menu

    def annotations(self):
        # XXX - add compiler warnings here, once we support that
        return []

    def links(self):
        # modules
        for name, id in self.top_level_mods():
            links = []
            for mod_name, line in self.scoped_items('modules', id):
                links.append(('struct', mod_name, "#%s" % line))
            for type_name, line in self.scoped_items('types', id):
                links.append(('type', type_name, "#%s" % line))
            for method_name, line in self.scoped_items('variables', id):
                links.append(('field', method_name, "#%s" % line))
            for method_name, line in self.scoped_items('functions', id):
                links.append(('method', method_name, "#%s" % line))
            if links:
                yield (20, name, links)

        # structs
        for name, id in self.top_level_scopes('struct'):
            links = []
            for field_name, line in self.scoped_items('variables', id):
                links.append(('field', field_name, "#%s" % line))
            # methods from impls
            sql = """
                SELECT fn.name, fn.file_line
                FROM functions AS fn, impl_defs AS impl
                WHERE fn.scopeid = impl.id AND
                    impl.refid = ?
                ORDER BY fn.file_line
                """
            for method_name, line in self.conn.execute(sql, (id,)):
                if len(method_name) == 0: continue
                links.append(('method', method_name, "#%s" % line))
            if links:
                yield (40, name, links)

        # traits
        for name, id in self.top_level_scopes('trait'):
            links = []
            for method_name, line in self.scoped_items('functions', id):
                links.append(('method', method_name, "#%s" % line))
            if links:
                yield (30, name, links)

        # enums
        for name, id in self.top_level_scopes('enum'):
            links = []
            for variant, line in self.scoped_items('variables', id):
                links.append(('field', variant, "#%s" % line))
            for variant, line in self.scoped_items('types', id):
                links.append(('field', variant, "#%s" % line))
            if links:
                yield (35, name, links)

        # functions
        links = []
        for name, line in self.top_level_items('functions'):
            links.append(('method', name, "#%s" % line))
        if links:
            yield (50, 'functions', links)

        # statics
        links = []
        for name, line in self.top_level_items('variables'):
            links.append(('field', name, "#%s" % line))
        if links:
            yield (60, 'statics', links)

    def top_level_items(self, kind):
        sql = """
            SELECT item.name, item.file_line
            FROM %s AS item
            WHERE item.file_id = ? AND
                (item.scopeid = 0 OR
                 EXISTS (SELECT 1 FROM modules AS mod WHERE item.scopeid = mod.id AND mod.def_file <> mod.file_id))
            ORDER BY item.file_line
            """%kind
        for name, line in self.conn.execute(sql, (self.file_id,)):
            if len(name) == 0: continue
            yield (name,line)

    def top_level_mods(self):
        sql = """
            SELECT name, id
            FROM modules AS m
            WHERE file_id = ? AND
                file_id = def_file AND
                (scopeid = 0 OR
                 EXISTS (SELECT 1 FROM modules AS mod WHERE m.scopeid = mod.id AND mod.def_file <> mod.file_id))
            ORDER BY file_line
            """
        for name, id in self.conn.execute(sql, (self.file_id,)):
            if len(name) == 0: continue
            yield (name,id)

    def top_level_scopes(self, kind):
        sql = """
            SELECT name, id
            FROM types
            WHERE kind = '%s' AND
                file_id = ? AND
                (scopeid = 0 OR
                 EXISTS (SELECT 1 FROM modules AS mod WHERE types.scopeid = mod.id AND mod.def_file <> mod.file_id))
            ORDER BY file_line
            """%kind
        for name, id in self.conn.execute(sql, (self.file_id,)):
            if len(name) == 0: continue
            yield (name,id)

    def scoped_items(self, kind, scope):
        sql = """
            SELECT name, file_line
            FROM %s
            WHERE scopeid == ?
            ORDER BY file_line
            """%kind
        for name, line in self.conn.execute(sql, (scope,)):
            if len(name) == 0: continue
            yield(name, line)


# helper method, extract the 'foo.com' from 'http://foo.com/bar.html'
def get_domain(url):
    start = url.find('//') + 2
    return url[start:url.find('/', start)]


# XXX Does anyone use anything other than rs nowadays?
_patterns = ('*.rs', '*.rc')
def htmlify(path, text):
    fname = os.path.basename(path)
    if any((fnmatch.fnmatchcase(fname, p) for p in _patterns)):
        # Get file_id, skip if not in database
        sql = "SELECT files.id FROM files WHERE path = ? LIMIT 1"
        row = _conn.execute(sql, (path,)).fetchone()
        if row:
            return RustHtmlifier(_tree, _conn, path, text, row[0])
    return None

__all__ = dxr.plugins.htmlifier_exports()
