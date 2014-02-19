import dxr.plugins
import os, sys
import fnmatch
import urllib, re

from dxr.utils import search_url


class ClangHtmlifier(object):
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

        # Extents for functions defined here
        sql = """
            SELECT extent_start, extent_end, qualname,
                EXISTS (SELECT targetid FROM targets WHERE funcid=functions.id) AS isvirtual
                FROM functions
              WHERE file_id = ?
        """
        for start, end, qualname, isvirtual in self.conn.execute(sql, args):
            yield start, end, (self.function_menu(qualname, isvirtual), qualname, None)

        # Extents for functions declared here
        sql = """
            SELECT decldef.extent_start,
                          decldef.extent_end,
                          functions.qualname,
                          (SELECT path FROM files WHERE files.id = functions.file_id),
                          functions.file_line,
                          EXISTS (SELECT targetid FROM targets WHERE funcid=functions.id) AS isvirtual
                FROM function_decldef AS decldef, functions
              WHERE decldef.defid = functions.id
                  AND decldef.file_id = ?
        """
        for start, end, qualname, path, line, isvirtual in self.conn.execute(sql, args):
            menu = self.function_menu(qualname, isvirtual)
            self.add_jump_definition(menu, path, line)
            yield start, end, (menu, qualname, None)

        # Extents for variables defined here
        sql = """
            SELECT extent_start, extent_end, qualname, value
                FROM variables
              WHERE file_id = ?
        """
        for start, end, qualname, value in self.conn.execute(sql, args):
            yield start, end, (self.variable_menu(qualname), qualname, value)

        # Extents for variables declared here
        sql = """
            SELECT decldef.extent_start,
                          decldef.extent_end,
                          variables.qualname,
                          variables.value,
                          (SELECT path FROM files WHERE files.id = variables.file_id),
                          variables.file_line
                FROM variable_decldef AS decldef, variables
              WHERE decldef.defid = variables.id
                  AND decldef.file_id = ?
        """
        for start, end, qualname, value, path, line in self.conn.execute(sql, args):
            menu = self.variable_menu(qualname)
            self.add_jump_definition(menu, path, line)
            yield start, end, (menu, qualname, value)

        # Extents for types defined here
        sql = """
            SELECT extent_start, extent_end, qualname, kind
                FROM types
              WHERE file_id = ?
        """
        for start, end, qualname, kind in self.conn.execute(sql, args):
            yield start, end, (self.type_menu(qualname, kind), qualname, None)

        # Extents for types declared here
        sql = """
            SELECT decldef.extent_start,
                          decldef.extent_end,
                          types.qualname,
                          types.kind,
                          (SELECT path FROM files WHERE files.id = types.file_id),
                          types.file_line
                FROM type_decldef AS decldef, types
              WHERE decldef.defid = types.id
                  AND decldef.file_id = ?
        """
        for start, end, qualname, kind, path, line in self.conn.execute(sql, args):
            menu = self.type_menu(qualname, kind)
            self.add_jump_definition(menu, path, line)
            yield start, end, (menu, qualname, None)

        # Extents for typedefs defined here
        sql = """
            SELECT extent_start, extent_end, qualname
                FROM typedefs
              WHERE file_id = ?
        """
        for start, end, qualname in self.conn.execute(sql, args):
            yield start, end, (self.typedef_menu(qualname), qualname, None)

        # Extents for namespaces defined here
        sql = """
            SELECT extent_start, extent_end, qualname
                FROM namespaces
              WHERE file_id = ?
        """
        for start, end, qualname in self.conn.execute(sql, args):
            yield start, end, (self.namespace_menu(qualname), qualname, None)

        # Extents for namespace aliases defined here
        sql = """
            SELECT extent_start, extent_end, qualname
                FROM namespace_aliases
              WHERE file_id = ?
        """
        for start, end, qualname in self.conn.execute(sql, args):
            yield start, end, (self.namespace_alias_menu(qualname), qualname, None)

        # Extents for macros defined here
        sql = """
            SELECT extent_start, extent_end, name, text
                FROM macros
              WHERE file_id = ?
        """
        for start, end, name, value in self.conn.execute(sql, args):
            yield start, end, (self.macro_menu(name), name, value)

        # Add references to types
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                          types.qualname,
                          types.kind,
                          (SELECT path FROM files WHERE files.id = types.file_id),
                          types.file_line
                FROM types, type_refs AS refs
              WHERE types.id = refs.refid AND refs.file_id = ?
        """
        for start, end, qualname, kind, path, line in self.conn.execute(sql, args):
            menu = self.type_menu(qualname, kind)
            self.add_jump_definition(menu, path, line)
            yield start, end, (menu, qualname, None)

        # Add references to typedefs
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                          typedefs.qualname,
                          (SELECT path FROM files WHERE files.id = typedefs.file_id),
                          typedefs.file_line
                FROM typedefs, typedef_refs AS refs
              WHERE typedefs.id = refs.refid AND refs.file_id = ?
        """
        for start, end, qualname, path, line in self.conn.execute(sql, args):
            menu = self.typedef_menu(qualname)
            self.add_jump_definition(menu, path, line)
            yield start, end, (menu, qualname, None)

        # Add references to functions
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                          functions.qualname,
                          (SELECT path FROM files WHERE files.id = functions.file_id),
                          functions.file_line,
                          EXISTS (SELECT targetid FROM targets WHERE funcid=functions.id) AS isvirtual
                FROM functions, function_refs AS refs
              WHERE functions.id = refs.refid AND refs.file_id = ?
        """
        for start, end, qualname, path, line, isvirtual in self.conn.execute(sql, args):
            menu = self.function_menu(qualname, isvirtual)
            self.add_jump_definition(menu, path, line)
            yield start, end, (menu, qualname, None)

        # Add references to variables
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                          variables.qualname,
                          variables.value,
                          (SELECT path FROM files WHERE files.id = variables.file_id),
                          variables.file_line
                FROM variables, variable_refs AS refs
              WHERE variables.id = refs.refid AND refs.file_id = ?
        """
        for start, end, qualname, value, path, line in self.conn.execute(sql, args):
            menu = self.variable_menu(qualname)
            self.add_jump_definition(menu, path, line)
            yield start, end, (menu, qualname, value)

        # Add references to namespaces
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                          namespaces.qualname,
                          (SELECT path FROM files WHERE files.id = namespaces.file_id),
                          namespaces.file_line
                FROM namespaces, namespace_refs AS refs
              WHERE namespaces.id = refs.refid AND refs.file_id = ?
        """
        for start, end, qualname, path, line in self.conn.execute(sql, args):
            menu = self.namespace_menu(qualname)
            yield start, end, (menu, qualname, None)

        # Add references to namespace aliases
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                          namespace_aliases.qualname,
                          (SELECT path FROM files WHERE files.id = namespace_aliases.file_id),
                          namespace_aliases.file_line
                FROM namespace_aliases, namespace_alias_refs AS refs
              WHERE namespace_aliases.id = refs.refid AND refs.file_id = ?
        """
        for start, end, qualname, path, line in self.conn.execute(sql, args):
            menu = self.namespace_alias_menu(qualname)
            self.add_jump_definition(menu, path, line)
            yield start, end, (menu, qualname, None)

        # Add references to macros
        sql = """
            SELECT refs.extent_start, refs.extent_end,
                          macros.name,
                          macros.text,
                          (SELECT path FROM files WHERE files.id = macros.file_id),
                          macros.file_line
                FROM macros, macro_refs AS refs
              WHERE macros.id = refs.refid AND refs.file_id = ?
        """
        for start, end, name, value, path, line in self.conn.execute(sql, args):
            menu = self.macro_menu(name)
            self.add_jump_definition(menu, path, line)
            yield start, end, (menu, name, value)

        # Link all the #includes in this file to the files they reference.
        for start, end, path in self.conn.execute(
                'SELECT extent_start, extent_end, path FROM includes '
                'INNER JOIN files ON files.id=includes.target_id '
                'WHERE includes.file_id = ?', args):
            yield start, end, ([{'html': 'Jump to file',
                                 'title': 'Jump to what is included here.',
                                 'href': self.tree.config.wwwroot + '/' +
                                         self.tree.name + '/source/' + path,
                                 'icon': 'jump'}], '', None)

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

    def add_jump_definition(self, menu, path, line):
        """ Add a jump to definition to the menu """
        # Definition url
        url = self.tree.config.wwwroot + '/' + self.tree.name + '/source/' + path
        url += "#%s" % line
        menu.insert(0, { 
            'html':   "Jump to definition",
            'title':  "Jump to the definition in '%s'" % os.path.basename(path),
            'href':   url,
            'icon':   'jump'
        })

    def type_menu(self, qualname, kind):
        """ Build menu for type """
        menu = []
        # Things we can do with qualname
        menu.append({
            'html':   "Find declarations",
            'title':  "Find declarations of this class",
            'href':   self.search("+type-decl:%s" % self.quote(qualname)),
            'icon':   'reference'  # FIXME?
        })
        if kind == 'class' or kind == 'struct':
            menu.append({
                'html':   "Find sub classes",
                'title':  "Find sub classes of this class",
                'href':   self.search("+derived:%s" % self.quote(qualname)),
                'icon':   'type'
            })
            menu.append({
                'html':   "Find base classes",
                'title':  "Find base classes of this class",
                'href':   self.search("+bases:%s" % self.quote(qualname)),
                'icon':   'type'
            })
        menu.append({
            'html':   "Find members",
            'title':  "Find members of this class",
            'href':   self.search("+member:%s" % self.quote(qualname)),
            'icon':   'members'
        })
        menu.append({
            'html':   "Find references",
            'title':  "Find references to this class",
            'href':   self.search("+type-ref:%s" % self.quote(qualname)),
            'icon':   'reference'
        })
        return menu


    def typedef_menu(self, qualname):
        """ Build menu for typedef """
        menu = []
        menu.append({
            'html':   "Find references",
            'title':  "Find references to this typedef",
            'href':   self.search("+type-ref:%s" % self.quote(qualname)),
            'icon':   'reference'
        })
        return menu


    def variable_menu(self, qualname):
        """ Build menu for a variable """
        menu = []
        menu.append({
            'html':   "Find declarations",
            'title':  "Find declarations of this variable",
            'href':   self.search("+var-decl:%s" % self.quote(qualname)),
            'icon':   'reference' # FIXME?
        })
        menu.append({
            'html':   "Find references",
            'title':  "Find reference to this variable",
            'href':   self.search("+var-ref:%s" % self.quote(qualname)),
            'icon':   'field'
        })
        # TODO Investigate whether assignments and usages is possible and useful?
        return menu


    def namespace_menu(self, qualname):
        """ Build menu for a namespace """
        menu = []
        menu.append({
            'html':   "Find definitions",
            'title':  "Find definitions of this namespace",
            'href':   self.search("+namespace:%s" % self.quote(qualname)),
            'icon':   'jump'
        })
        menu.append({
            'html':   "Find references",
            'title':  "Find references to this namespace",
            'href':   self.search("+namespace-ref:%s" % self.quote(qualname)),
            'icon':   'reference'
        })
        return menu


    def namespace_alias_menu(self, qualname):
        """ Build menu for a namespace """
        menu = []
        menu.append({
            'html':   "Find references",
            'title':  "Find references to this namespace alias",
            'href':   self.search("+namespace-alias-ref:%s" % self.quote(qualname)),
            'icon':   'reference'
        })
        return menu


    def macro_menu(self, name):
        menu = []
        # Things we can do with macros
        menu.append({
            'html':   "Find references",
            'title':  "Find references to macros with this name",
            'href':    self.search("+macro-ref:%s" % name),
            'icon':   'reference'
        })
        return menu


    def function_menu(self, qualname, isvirtual):
        """ Build menu for a function """
        menu = []
        # Things we can do with qualified name
        menu.append({
            'html':   "Find declarations",
            'title':  "Find declarations of this function",
            'href':   self.search("+function-decl:%s" % self.quote(qualname)),
            'icon':   'reference'  # FIXME?
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
        menu.append({
            'html':   "Find references",
            'title':  "Find references to this function",
            'href':   self.search("+function-ref:%s" % self.quote(qualname)),
            'icon':   'reference'
        })
        if isvirtual:
            menu.append({
                'html':   "Find overridden",
                'title':  "Find functions that this function overrides",
                'href':   self.search("+overridden:%s" % self.quote(qualname)),
                'icon':   'method'
            })
            menu.append({
                'html':   "Find overrides",
                'title':  "Find overrides of this function",
                'href':   self.search("+overrides:%s" % self.quote(qualname)),
                'icon':   'method'
            })
        return menu


    def annotations(self):
        icon = "background-image: url('%s/static/icons/warning.png');" % self.tree.config.wwwroot
        sql = "SELECT msg, opt, file_line FROM warnings WHERE file_id = ? ORDER BY file_line"
        for msg, opt, line in self.conn.execute(sql, (self.file_id,)):
            if opt:
                msg = msg + " [" + opt + "]"
            yield line, {
                'title': msg,
                'class': "note note-warning",
                'style': icon
            }

    def links(self):
        # For each type add a section with members
        sql = "SELECT name, id, file_line, kind FROM types WHERE file_id = ?"
        for name, tid, line, kind in self.conn.execute(sql, (self.file_id,)):
            if len(name) == 0: continue
            links = []
            links += list(self.member_functions(tid))
            links += list(self.member_variables(tid))

            # Sort them by line
            links = sorted(links, key = lambda link: link[1])

            # Make sure we have a sane limitation of kind
            if kind not in ('class', 'struct', 'enum', 'union'):
                print >> sys.stderr, "kind '%s' was replaced for 'type'!" % kind
                kind = 'type'

            # Add the outer type as the first link
            links.insert(0, (kind, name, "#%s" % line))

            # Now return the type
            yield (30, name, links)

        # Add all macros to the macro section
        links = []
        sql = "SELECT name, file_line FROM macros WHERE file_id = ?"
        for name, line in self.conn.execute(sql, (self.file_id,)):
            links.append(('macro', name, "#%s" % line))
        if links:
            yield (100, "Macros", links)

    def member_functions(self, tid):
        """ Fetch member functions given a type id """
        sql = """
            SELECT name, file_line
            FROM functions
            WHERE file_id = ? AND scopeid = ?
        """
        for name, line in self.conn.execute(sql, (self.file_id, tid)):
            # Skip nameless things
            if len(name) == 0: continue
            yield 'method', name, "#%s" % line

    def member_variables(self, tid):
        """ Fetch member variables given a type id """
        sql = """
            SELECT name, file_line
            FROM variables
            WHERE file_id = ? AND scopeid = ?
        """
        for name, line in self.conn.execute(sql, (self.file_id, tid)):
            # Skip nameless things
            if len(name) == 0: continue
            yield 'field', name, "#%s" % line


_tree = None
_conn = None
def load(tree, conn):
    global _tree, _conn
    _tree = tree
    _conn = conn


_patterns = ('*.c', '*.cc', '*.cpp', '*.cxx', '*.h', '*.hpp')
def htmlify(path, text):
    fname = os.path.basename(path)
    if any((fnmatch.fnmatchcase(fname, p) for p in _patterns)):
        # Get file_id, skip if not in database
        sql = "SELECT files.id FROM files WHERE path = ? LIMIT 1"
        row = _conn.execute(sql, (path,)).fetchone()
        if row:
            return ClangHtmlifier(_tree, _conn, path, text, row[0])
    return None


__all__ = dxr.plugins.htmlifier_exports()
