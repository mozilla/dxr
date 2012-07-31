import dxr.plugins
import os, sys
import fnmatch
import clang.tokenizers as tokenizers
import urllib, re

class ClangHtmlifier:
  """ Pygmentizer add syntax regions for file """
  def __init__(self, tree, conn, path, text, file_id):
    self.tree    = tree
    self.conn    = conn
    self.path    = path
    self.text    = text
    self.file_id = file_id

  def regions(self):
    # Let's not do any syntax stuff here, it doesn't really make any sense
    # when syntax is already done in pygmentize
    # I suppose this is only useful if we want to highlight something special,
    # like warnings, or code coverage, or who knows...
    return []


  def refs(self):
    """ Generate reference menues """
    # We'll need this argument for all queries here
    args = (self.file_id,)

    # Extents for functions defined here
    sql = """
      SELECT extent_start, extent_end, funcid, fqualname
        FROM functions
       WHERE file_id = ?
    """
    for start, end, funcid, fqualname in self.conn.execute(sql, args):
      yield start, end, self.function_menu(funcid, fqualname)

    # Extents for variables defined here
    sql = """
      SELECT extent_start, extent_end, varid, vname
        FROM variables
       WHERE file_id = ?
    """
    for start, end, varid, vname in self.conn.execute(sql, args):
      yield start, end, self.variable_menu(varid, vname)

    # Extents for types defined here
    sql = """
      SELECT extent_start, extent_end, tid, tqualname
        FROM types
       WHERE file_id = ?
    """
    for start, end, tid, tqualname in self.conn.execute(sql, args):
      yield start, end, self.type_menu(tid, tqualname)

    # Extents for macros defined here
    sql = """
      SELECT file_line, file_col, macroid, macroname
        FROM macros
       WHERE file_id = ?
    """
    for line, col, macroid, macroname in self.conn.execute(sql, args):
      # TODO Refactor macro table and remove the (line, col) scheme!
      start = (line, col)
      end   = (line, col + len(macroname))
      yield start, end, self.macro_menu(macroid, macroname)

    # Extents for references in this file
    sql = """
      SELECT extent_start, extent_end, refid
        FROM refs
       WHERE refid IS NOT NULL AND file_id = ?
    """ #TODO Refactor references table, refid IS NOT NULL shouldn't be needed!
    cache = {}
    for start, end, refid in self.conn.execute(sql, args):
      # Try to fetch from cache
      menu = cache.get(int(refid), False)
      if menu is False:
        menu = self.ref_menu(refid)
        # Store to cache, also stores None if no menu
        cache[int(refid)] = menu
      if menu:
        yield start, end, menu

    # Hack to add links for #includes
    # TODO This should be handled in the clang extension we don't know the
    # include paths here, and we cannot resolve includes correctly.
    pattern = re.compile('\#[\s]*include[\s]*[<"](\S+)[">]')
    tokenizer = tokenizers.CppTokenizer(self.text)
    for token in tokenizer.getTokens():
      if token.token_type == tokenizer.PREPROCESSOR and 'include' in token.name:
        match = pattern.match(token.name)
        if match is None:
          continue
        inc_name = match.group(1)
        sql = "SELECT path FROM files WHERE path LIKE ?"
        rows = self.conn.execute(sql, ("%%%s" % (inc_name),)).fetchall()

        if rows is None or len(rows) == 0:
          basename = os.path.basename(inc_name)
          rows = self.conn.execute(sql, ("%%/%s" % (basename),)).fetchall()

        if rows is not None and len(rows) == 1:
          path  = rows[0][0]
          start = token.start + match.start(1)
          end   = token.start + match.end(1)
          url   = self.tree.config.wwwroot + '/' + self.tree.name + '/' + path
          menu  = [{
            'text':   "Jump to file",
            'title':  "Jump to what is likely included there",
            'href':   url,
            'icon':   'jump'
          },]
          yield start, end, menu
      else:
        continue

    # Test hack for declaration/definition jumps
    #sql = """
    #  SELECT extent_start, extent_end, defid
    #    FROM decldef
    #   WHERE file_id = ?
    #"""
    #

  def search(self, query):
    """ Auxiliary function for getting the search url for query """
    url = self.tree.config.wwwroot + "/search?tree=" + self.tree.name
    url += "&q=" + urllib.quote(query)
    return url


  def ref_menu(self, rid):
    """ Generate a menu for a reference """
    # Since reference ids are ids of either type, variable, function or macro
    # We just try them all, one by one, order by what we consider most likely
    menu = None

    # Check if it's a variable
    if not menu:
      sql = """
        SELECT vname, file_id, file_line
          FROM variables
         WHERE varid = ? LIMIT 1
      """
      row = self.conn.execute(sql, (rid,)).fetchone()
      if row:
        vname, file_id, line = row
        menu = self.variable_menu(rid, vname)

    # Check if it's a function
    if not menu:
      sql = """
        SELECT fqualname, file_id, file_line
          FROM functions
         WHERE funcid = ? LIMIT 1
      """
      row = self.conn.execute(sql, (rid,)).fetchone()
      if row:
        fqualname, file_id, line = row
        menu = self.function_menu(rid, fqualname)

    # Check if it's a macro
    if not menu:
      sql = """
        SELECT macroname, file_id, file_line
          FROM macros
         WHERE macroid = ? LIMIT 1
      """
      row = self.conn.execute(sql, (rid,)).fetchone()
      if row:
        macroname, file_id, line = row
        menu = self.macro_menu(rid, macroname)

    # Check if it's a type
    if not menu:
      sql = """
        SELECT tqualname, file_id, file_line
          FROM types
         WHERE tid = ? LIMIT 1
      """
      row = self.conn.execute(sql, (rid,)).fetchone()
      if row:
        tqualname, file_id, line = row
        menu = self.type_menu(rid, tqualname)

    # Add jump to definition
    if menu:
      # Okay, lookup path of definition
      sql = "SELECT path FROM files WHERE files.ID = ? LIMIT 1"
      (path,) = self.conn.execute(sql, (file_id,)).fetchone()
      # Definition url
      url = self.tree.config.wwwroot + '/' + self.tree.name + '/' + path
      url += "#l%s" % line
      menu.insert(0, { 
        'text':   "Jump to definition",
        'title':  "Jump to the definition of this reference",
        'href':   url,
        'icon':   'jump'
      })

    # Okay we don't know what it is
    sql = "SELECT extent_start, extent_end FROM refs WHERE refid = ?"
    start, end = self.conn.execute(sql, (rid,)).fetchone()
    src = self.text[start:end]
    # TODO Refactor refs, such that we don't have things that doesn't resolve!
    print >> sys.stderr, "Failed to resolve refid '%s' for '%s'" % (rid, src)
    return None


  def type_menu(self, tid, tqualname):
    """ Build menu for type """
    menu = []
    # Things we can do with tqualname
    menu.append({
      'text':   "Find sub classes",
      'title':  "Find sub classes of this class",
      'href':   self.search("+derived:%s" % tqualname),
      'icon':   'type'
    })
    menu.append({
      'text':   "Find base classes",
      'title':  "Find base classes of this class",
      'href':   self.search("+bases:%s" % tqualname),
      'icon':   'type'
    })
    menu.append({
      'text':   "Find members",
      'title':  "Find members of this class",
      'href':   self.search("+member:%s" % tqualname),
      'icon':   'members'
    })
    menu.append({
      'text':   "Find references",
      'title':  "Find references to this class",
      'href':   self.search("+type-ref:%s" % tqualname),
      'icon':   'reference'
    })
    return menu


  def variable_menu(self, varid, vname):
    """ Build menu for a variable """
    menu = []
    # Well, what more than references can we do?
    menu.append({
      'text':   "Find references",
      'title':  "Find reference to this variable",
      'href':   self.search("+var-ref:%s" % vname),
      'icon':   'field'
    })
    # TODO Investigate whether assignments and usages is possible and useful?
    return menu


  def macro_menu(self, macroid, macroname):
    menu = []
    # Things we can do with macros
    self.tree.config.wwwroot
    menu.append({
      'text':   "Find references",
      'title':  "Find references to macros with this name",
      'href':    self.search("+macro-ref:%s" % macroname),
      'icon':   'reference'
    })
    return menu


  def function_menu(self, funcid, fqualname):
    """ Build menu for a function """
    menu = []
    # Things we can do with qualified name
    menu.append({
      'text':   "Find callers",
      'title':  "Find functions that calls this function",
      'href':   self.search("+callers:%s" % fqualname),
      'icon':   'method'
    })
    menu.append({
      'text':   "Find callees",
      'title':  "Find functions that are called by this function",
      'href':   self.search("+called-by:%s" % fqualname),
      'icon':   'method'
    })
    menu.append({
      'text':   "Find references",
      'title':  "Find references of this function",
      'href':   self.search("+function-ref:%s" % fqualname),
      'icon':   'reference'
    })
    #TODO Jump between declaration and definition
    return menu


  def annotations(self):
    sql = "SELECT wmsg, file_line FROM warnings WHERE file_id = ?"
    for msg, line in self.conn.execute(sql, (self.file_id,)):
      yield line, {'title': msg}, 'warning'


  def links(self):
    # For each type add a section with members
    sql = "SELECT tname, tid, file_line FROM types WHERE file_id = ?"
    for tname, tid, tline in self.conn.execute(sql, (self.file_id,)):
      links = []
      links += list(self.member_functions(tid))
      links += list(self.member_variables(tid))

      # Sort them by line
      links = sorted(links, key = lambda link: link[3])

      # Add the outer type as the first link
      links.insert(0, ('type', tname, self.path, tline))

      # Now return the type
      yield (30, tname, links)

    # Add all macros to the macro section
    links = []
    sql = "SELECT macroname, file_line FROM macros WHERE file_id = ?"
    for macro, line in self.conn.execute(sql, (self.file_id,)):
      links.append(('macro', macro, self.path, line))
    if links:
      yield (100, "Macros", links)


  def member_functions(self, tid):
    """ Fetch member functions given a type id """
    sql = """
      SELECT fname, file_line
      FROM functions
      WHERE file_id = ? AND scopeid = ?
    """
    for fname, line in self.conn.execute(sql, (self.file_id, tid)):
      yield 'method', fname, self.path, line


  def member_variables(self, tid):
    """ Fetch member variables given a type id """
    sql = """
      SELECT vname, file_line
      FROM variables
      WHERE file_id = ? AND scopeid = ?
    """
    for vname, line in self.conn.execute(sql, (self.file_id, tid)):
      yield 'field', vname, self.path, line


#tokenizers = None
_patterns = ('*.c', '*.cc', '*.cpp', '*.h', '*.hpp')
def htmlify(tree, conn, path, text):
  #if not tokenizers:
  #  # HACK around the fact that we can't load modules from plugin folders
  #  # we'll probably need to fix this later,
  #  #tpath = os.path.join(tree.config.plugin_folder, "cxx-clang", "tokenizers.py")
  #  #imp.load_source("tokenizers", tpath)

  fname = os.path.basename(path)
  if any((fnmatch.fnmatchcase(fname, p) for p in _patterns)):
    # Get file_id, skip if not in database
    sql = "SELECT files.ID FROM files WHERE path = ? LIMIT 1"
    row = conn.execute(sql, (path,)).fetchone()
    if row:
      return ClangHtmlifier(tree, conn, path, text, row[0])
  return None


__all__ = dxr.plugins.htmlifier_exports()
