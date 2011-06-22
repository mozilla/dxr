import os

def in_path(exe):
  """ Returns true if the executable can be found in the given path.
      Equivalent to which, except that it doesn't check executability. """
  path = os.environ['PATH'].split(':')
  return any([os.path.exists(os.path.join(p, exe)) for p in path])

def default_post_process(srcdir, objdir):
  """ Collect data from processing files in the source and build directories.

      The return value of this step is fairly loosely defined, but as a general
      rule of the thumb, it should be a dictionary that contains an equivalent
      representation that can be stored in the database, and there should
      probably be a fast lookup mechanisms for data found in a file."""
  return {"byfile": {}}

def default_sqlify(blob):
  """ Return an iterable of SQL statements from collected source data.

      The blob is the object returned by post_process. Output data will be
      filtered for uniqueness via a set, so the order of statements is not
      necessarily what will be run in order."""
  return []

def default_can_use(treecfg):
  """ Returns True if this plugin can be used for the given tree."""
  return True

def default_get_htmlifiers():
  """ Returns source code htmlifiers that this plugin uses.
      
      The return value is a dictionary of { file-ending: htmlifier } values.
      An htmlifier is a dictionary consisting of the following keys, whose
      values are functions which receive (blob, srcpath, treeconfig)
        blob -- The return value of post_process
        srcpath -- The path of the source file
        treeconfig -- A configuration object for the tree
      get_sidebar_links - An iterable of tuples to be used in the sidebar
        (name, line, title[, img, [container]])
        name -- The display name of the item
        line -- The line on which the item is defined in the file
        title -- The tooltip to display on hovre
        img -- An optional image path to use for the link
        container -- The name of the logical container for this item
      get_link_regions - An iterable of tuples to be used for making links
        (start, end, type, {attr:val})
        start -- The index of the first character in the link
        end -- The index of the first character not in the link
        type -- The type query to use for get_info.cgi
        {attr:val} -- Additional properties which will be passed into
                      get_info.cgi
      get_line_annotations - An iterable of tuples for annotating lines
        (line, {attr:val})
        line -- The line of the file
        {attr:val} -- Additional properties to set on the line object
      get_syntax_regions - An iterable of tuples to be used for syntax
        (start, end, kind)
        start -- The index of the first character in the region
        end -- The index of the first character not in the region
        kind -- The class to use for syntax region.
          k - Keywords
          str - String literals
          c - Comments
          p - Preprocessor
      Note that indexes into a file can either be the byte offset or a
      (line, col) tuple, depending on which is easier for you to generate.

      In addition, any htmlifier that contains the key 'no-override' will be
      run in addition to the first htmlifier found.
      """
  def noop(blob, srcpath, treecfg):
    return []
  return {}

class Schema:
  """ A representation of SQL table data.

      This class allows for easy ways to handle SQL data given blob information,
      and is probably the preferred format for storing the schema.

      The input schema is a dictionary whose keys are the table names and whose
      values are dictionaries for table schemas.
      
      This class interprets blob data as a dictionary of tables; each table is
      either a dictionary of {key:row} elements or a list of {key:row} elements.
      The rows are dictionaries of {col:value} elements; only those values that
      are actually present in the schema will be serialized in the get_data_sql
      function. """
  def __init__(self, schema):
    """ Creates a new schema with the given definition. See the class docs for
        this and SchemaTable for what syntax looks like. """
    self.tables = {}
    for tbl in schema:
      self.tables[tbl] = SchemaTable(tbl, schema[tbl])

  def get_create_sql(self):
    """ Returns the SQL that creates the tables in this schema. """
    return '\n'.join([tbl.get_create_sql() for tbl in self.tables.itervalues()])

  def get_data_sql(self, blob):
    """ Returns the SQL that inserts data into tables given a blob. """
    for tbl in self.tables:
      if tbl in blob:
        sqliter = self.tables[tbl].get_data_sql(blob[tbl])
        for sql in sqliter:
          yield sql


class SchemaTable:
  """ A table schema dictionary has column names as keys and information tuples
      as values: "col": (type, mayBeNull)
        type is the type string (e.g., VARCHAR(256) or INTEGER), although it
          may have special values
        mayBeNull is an optional attribute that specifies if the column may
          contain null values. not specifying is equivalent to True
      
      Any column name that begins with a `_' is metadata about the table:
        _key: the result tuple is a tuple for the primary key of the table.

      Special values for type strings are as follows:
        _location: A file:loc[:col] value for the column.

      Since the order of columns matter in SQL and python dicts are unordered,
      we will accept a list or tuple of tuples as an alternative specifier:
      "table": [
        ("col", type, False),
        ("col2", (type, False)),
        ...
  """
  def __init__(self, tblname, tblschema):
    self.name = tblname
    self.key = None
    self.columns = []
    defaults = ['VARCHAR(256)', True]
    for col in tblschema:
      if isinstance(tblschema, tuple) or isinstance(tblschema, list):
        col, spec = col[0], col[1:]
      else:
        spec = tblschema[col]
      if not isinstance(spec, tuple):
        spec = (spec,)
      if col == '_key':
        self.key = spec
      elif col[0] != '_':
        # if spec is deficient, we need to full it in with default tuples
        values = list(spec)
        if len(spec) < len(defaults):
          values.extend(defaults[len(spec):])
        self.columns.append((col, spec))

  def get_create_sql(self):
    sql = 'DROP TABLE IF EXISTS %s;\n' % (self.name)
    sql += 'CREATE TABLE %s (\n  ' % (self.name)
    colstrs = []
    special_types = {
      '_location': 'VARCHAR(256)'
    }
    for col, spec in self.columns:
      specsql = col + ' '
      if spec[0][0] == '_':
        specsql += special_types[spec[0]]
      else:
        specsql += spec[0]
      if len(spec) > 1 and spec[1] == False:
        specsql += ' NOT NULL'
      colstrs.append(specsql)
    if self.key is not None:
      colstrs.append('PRIMARY KEY (%s)' % ', '.join(self.key))
    sql += ',\n  '.join(colstrs)
    sql += '\n);\n'
    return sql

  def get_data_sql(self, blobtbl):
    it = isinstance(blobtbl, dict) and blobtbl.itervalues() or blobtbl
    colset = set(col[0] for col in self.columns)
    sqlset = set()
    for row in it:
      # Only add the keys in the columns
      keys = colset.intersection(row.iterkeys())
      sqlset.add('INSERT INTO %s (%s) VALUES (%s);' % (self.name,
        ','.join(keys), ','.join(repr(row[k]) for k in keys)))
    return iter(sqlset)


def make_get_schema_func(schema):
  """ Returns a function that satisfies get_schema's contract from the given
      schema object. """
  def get_schema():
    # Iterate over all tables
    return schema.get_create_sql()
  return get_schema

def required_exports():
  """ Returns the required exports for a module, for use as __all__. """
  return ['post_process', 'sqlify', 'can_use', 'get_htmlifiers', 'get_schema']
