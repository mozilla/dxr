class Schema(object):
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


class SchemaTable(object):
    """ A table schema dictionary has column names as keys and information tuples
        as values: "col": (type, mayBeNull)
          type is the type string (e.g., VARCHAR(256) or INTEGER), although it
            may have special values
          mayBeNull is an optional attribute that specifies if the column may
            contain null values. not specifying is equivalent to True
      
        Any column name that begins with a `_' is metadata about the table:
          _key: the result tuple is a tuple for the primary key of the table.

        Special values for type strings are as follows:
          _location: A file:loc[:col] value for the column. A boolean element
              in the tuple declares whether a compound index of (file ID, line,
              column) should be added.

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
            sql += 'CREATE INDEX %s_%s_index on %s (%s);\n' % (self.name, '_'.join(self.index), self.name, ','.join(self.index))
        if self.needFileKey is True:
            has_extents = 'extent_start' in [x[0] for x in self.columns]
            sql += ('CREATE UNIQUE INDEX %s_file_index on %s (file_id, file_line, file_col%s);' %
                    (self.name, self.name, ', extent_start, extent_end' if has_extents else ''))
        return sql

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
