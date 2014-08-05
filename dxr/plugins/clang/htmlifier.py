import os, sys
import fnmatch
import urllib, re
from itertools import chain
from operator import itemgetter

from funcy import compose, constantly

import dxr.plugins
from dxr.utils import search_url


class ClangHtmlifier(object):
    def __init__(self, tree, condensed):
        self.tree    = tree
        self.condensed = condensed

    def regions(self):
        return []

    def _common_ref(self, create_menu, view, get_val=constantly(None)):
        for prop in view(self.condensed):
            start, end = prop['span']
            menu = create_menu(prop)
            src, line, _ = start
            if src is not None:
                self.add_jump_definition(menu, src, line)
            yield start, end, (self.func(prop), get_val(prop))

    def refs(self):
        """ Generate reference menus """
        # We'll need this argument for all queries here
        # Extents for functions defined here
        itemgetter2 = lambda x y : compose(itemgetter(y), itemgetter(x))
        type_getter = lambda x: compose(chain, dict.values, itemgetter(x))
        return chain(
            self._common_ref(self.function_menu, itemgetter2('ref', 'function')),
            self._common_ref(self.variable_menu, itemgetter2('ref', 'variable')),
            self._common_ref(self.type_menu, type_getter('type')),
            self._common_ref(self.type_menu, type_getter('decldef')),
            self._common_ref(self.type_menu, itemgetter('typedefs')),
            self._common_ref(self.namespace_menu, itemgetter('namespace')),
            self._common_ref(self.namespace_alias_menu,
                             itemgetter('namespace_aliases')),
            self._common_ref(self.macro_menu, itemgetter('macro'),
                             itemgetter('text'))
            self._include_ref()
        )

    def include_menu(self, props):
        (path, _, _), _ = props['span']
        return {'html': 'Jump to file',
                'title': 'Jump to what is included here.',
                'href': self.tree.config.wwwroot + '/' + self.tree.name
                \ + '/source/' + path,
                'icon': 'jump'}

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

    def variable_menu(self, props):
        """ Build menu for a variable """
        qualname = props['qualnam']
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

    def namespace_menu(self, props):
        """ Build menu for a namespace """
        qualname = props['qualname']
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

    def namespace_alias_menu(self, props):
        """ Build menu for a namespace """
        qualname = props['qualname']
        menu = []
        menu.append({
            'html':   "Find references",
            'title':  "Find references to this namespace alias",
            'href':   self.search("+namespace-alias-ref:%s" % self.quote(qualname)),
            'icon':   'reference'
        })
        return menu

    def macro_menu(self, props):
        name = props['name']
        menu = []
        # Things we can do with macros
        menu.append({
            'html':   "Find references",
            'title':  "Find references to macros with this name",
            'href':    self.search("+macro-ref:%s" % name),
            'icon':   'reference'
        })
        return menu

    def function_menu(self, func):
        """ Build menu for a function """
        qualname = func['qualname']
        isvirtual = 'override' in func
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
            return ClangHtmlifier(_tree, _conn, row[0])
    return None


__all__ = dxr.plugins.htmlifier_exports()
