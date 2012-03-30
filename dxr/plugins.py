import dxr.languages
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

def default_pre_html_process(treecfg, blob):
  """ Called immediately before htmlifiers are first run. """
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

  def get_insert_sql(self, tblname, args):
    return self.tables[tblname].get_insert_sql(args)

  def get_data_sql(self, blob):
    """ Returns the SQL that inserts data into tables given a blob. """
    for tbl in self.tables:
      if tbl in blob:
        sqliter = self.tables[tbl].get_data_sql(blob[tbl])
        for sql in sqliter:
          yield sql

  def get_empty_blob(self):
    """ Returns an empty blob for this schema, using dicts for the table. """
    return dict((name, {}) for name in self.tables)


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
    self.index = None
    self.fkeys = []
    self.columns = []
    self.needLang = False
    self.needFileKey = False
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
      elif col == '_fkey':
        self.fkeys.append(spec)
      elif col == '_index':
        self.index = spec
      elif col == '_location':
        if len(spec) <= 1:
          prefix = ''
        else:
          prefix = spec[1] + "_"

        self.columns.append((prefix + "file_id", ["INTEGER", True]))
        self.columns.append((prefix + "file_line", ["INTEGER", True]))
        self.columns.append((prefix + "file_col", ["INTEGER", True]))
        self.needFileKey = spec[0]
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
      '_language': 'VARCHAR(32)'
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

    if self.needFileKey is True:
      colstrs.append('FOREIGN KEY (file_id) REFERENCES files(ID)')

    for spec in self.fkeys:
      colstrs.append('FOREIGN KEY (%s) REFERENCES %s(%s)' % (spec[0], spec[1], spec[2]))
    if self.key is not None:
      colstrs.append('PRIMARY KEY (%s)' % ', '.join(self.key))
    sql += ',\n  '.join(colstrs)
    sql += '\n);\n'
    if self.index is not None:
      sql += 'CREATE UNIQUE INDEX %s_index on %s (%s);\n' % (self.name, self.name, ','.join(self.index))
    if self.needFileKey is True:
      sql += 'CREATE UNIQUE INDEX %s_file_index on %s (file_id, file_line, file_col);' % (self.name, self.name)
    return sql

  def get_data_sql(self, blobtbl):
    it = isinstance(blobtbl, dict) and blobtbl.itervalues() or blobtbl
    colset = set(col[0] for col in self.columns)
    for row in it:
      # Only add the keys in the columns
      keys = colset.intersection(row.iterkeys())
      args = tuple(row[k] for k in keys)
      yield ('INSERT OR IGNORE INTO %s (%s) VALUES (%s);' % (self.name,
        ','.join(keys), ','.join('?' for k in keys)), args)

  def get_insert_sql(self, args):
    colset = set(col[0] for col in self.columns)
    unwanted = []

    # Only add the keys in the columns
    for key in args.iterkeys():
      if key not in colset:
        unwanted.append(key)

    for key in unwanted:
      del args[key]

    return ('INSERT OR IGNORE INTO %s (%s) VALUES (%s)' %
            (self.name, ','.join(args.keys()), ','.join('?' for k in range(0, len(args)))),
            args.values())

def make_get_schema_func(schema):
  """ Returns a function that satisfies get_schema's contract from the given
      schema object. """
  def get_schema():
    # Iterate over all tables
    return schema.get_create_sql()
  return get_schema

def required_exports():
  """ Returns the required exports for a module, for use as __all__. """
  return ['post_process', 'build_database', 'sqlify', 'can_use', 'get_htmlifiers', 'get_schema',
    'pre_html_process']

last_id = 0
def next_global_id():
  """ Returns a unique identifier that is unique compared to other IDs. """
  global last_id
  last_id += 1
  return last_id

language_by_file = None

def break_into_files(blob, tablelocs):
  global language_by_file

  # The following method builds up the file table
  def add_to_files(inblob, cols):
    filetable = {}
    for tblname, lockey in cols.iteritems():
      intable = inblob[tblname]
      tbliter = isinstance(intable, dict) and intable.itervalues() or intable
      for row in tbliter:
        fname = row[lockey].split(":")[0]
        try:
          tbl = filetable[fname]
        except KeyError:
          tbl = filetable[fname] = dict((col, []) for col in cols)
        tbl[tblname].append(row)
    return filetable

  # Build the map for total stuff
  standard_keys = {
    'scopes': 'sloc',
    'functions': 'floc',
    'variables': 'vloc',
    'types': 'tloc'
  }
  if language_by_file is None:
    language_by_file = add_to_files(dxr.languages.language_data, standard_keys)

  # Build our map for a specific plugin
  perfile = add_to_files(blob, tablelocs)
  for fname, table in perfile.iteritems():
    if fname in language_by_file:
      table.update(language_by_file[fname])
    else:
      table.update((key, []) for key in standard_keys)
  return perfile
