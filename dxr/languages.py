import dxr.plugins

# The following schema is the common global schema, so no matter which plugins
# are used, this schema will always be present. Most tables have a language
# column which indicates the source language that the type is written in.
language_schema = dxr.plugins.Schema({
  # Scope definitions: a scope is anything that is both interesting (i.e., not
  # a namespace) and can contain other objects. The IDs for this scope should be
  # IDs in other tables as well; the table its in can disambiguate which type of
  # scope you're looking at.
  "files" : [
      ("ID", "INTEGER", False),
      ("path", "VARCHAR(1024)", True),
      ("_key", "ID"),
      ("_index", "path")
  ],
  "scopes": [
    ("scopeid", "INTEGER", False),    # An ID for this scope
    ("sname", "VARCHAR(256)", True),  # Name of the scope
    ("language", "_language", False), # The language of the scope
    ("_location", True),
    ("_key", "scopeid")
  ],
  # Type definitions: anything that defines a type per the relevant specs.
  "types": [
    ("tid", "INTEGER", False),            # Unique ID for the type
    ("scopeid", "INTEGER", True),        # Scope this type is defined in
    ("tname", "VARCHAR(256)", False),     # Simple name of the type
    ("tqualname", "VARCHAR(256)", False), # Fully-qualified name of the type
    ("tkind", "VARCHAR(32)", True),       # Kind of type (e.g., class, union)
    ("language", "_language", True),     # Language of the type
    ("_location", True),
    ("_key", "tid"),
    ("_fkey", "scopeid", "scopes", "scopeid")
#    ("_index", "tqualname", "tloc")
  ],
  # Inheritance relations: note that we store the full transitive closure in
  # this table, so if A extends B and B extends C, we'd have (A, C) stored in
  # the table as well; this is necessary to make SQL queries work, since there's
  # no "transitive closure lookup expression".
  "impl": [
    ("tbase", "INTEGER", False),      # tid of base type
    ("tderived", "INTEGER", False),   # tid of derived type
    ("inhtype", "VARCHAR(32)", True), # Type of inheritance; NULL is indirect
    ("_key", "tbase", "tderived")
  ],
  # Functions: functions, methods, constructors, operator overloads, etc.
  "functions": [
    ("funcid", "INTEGER", False),         # Function ID (also in scopes)
    ("scopeid", "INTEGER", True),        # Scope defined in
    ("fname", "VARCHAR(256)", False),     # Short name (no args)
    ("fqualname", "VARCHAR(512)", False), # Fully qualified name, excluding args
    ("fargs", "VARCHAR(256)", False),     # Argument string, including parens
    ("ftype", "VARCHAR(256)", False),     # Full return type, as a string
    ("modifiers", "VARCHAR(256)", True),  # Modifiers (e.g., private)
    ("language", "_language", True),     # Language of the function
    ("_location", True),
    ("_key", "funcid"),
    ("_fkey", "scopeid", "scopes", "scopeid"),
#    ("_index", "fqualname", "floc")
  ],
  # Variables: class, global, local, enum constants; they're all in here
  # Variables are of course not scopes, but for ease of use, they use IDs from
  # the same namespace, no scope will have the same ID as a variable and v.v.
  "variables": [
    ("varid", "INTEGER", False),         # Variable ID
    ("scopeid", "INTEGER", True),       # Scope defined in
    ("vname", "VARCHAR(256)", False),    # Short name
    ("vtype", "VARCHAR(256)", True),     # Full type (including pointer stuff)
    ("modifiers", "VARCHAR(256)", True), # Modifiers for the declaration
    ("language", "_language", True),    # Language of the function
    ("_location", True),
    ("_key", "varid"),
    ("_fkey", "scopeid", "scopes", "scopeid"),
#    ("_index", "vname", "vloc")
  ],
  "crosslang": [
    ("canonid", "INTEGER", False),
    ("otherid", "INTEGER", False),
    ("otherlanguage", "VARCHAR(32)", False),
    ("_key", "otherid")
  ],
})

# Build the blob for the language data
# All of the tables are lists of rows, except for crosslang which is a dict of
# ref id -> canonical id
language_data = language_schema.get_empty_blob()
tableids = {
  'scopes': 'scopeid',
  'types': 'tid',
  'functions': 'funcid',
  'variables': 'varid',
  'crosslang': 'canonid'
}
for table in language_data:
  if table not in tableids:
    language_data[table] = []

def get_standard_schema():
  ''' Returns the standard schema for multiple language support. '''
  return language_schema.get_create_sql()

def register_language_table(language, tablename, table):
  ''' Add the rows in the table to the language schema. '''
  tableit = isinstance(table, dict) and table.itervalues() or table
  dest = language_data[tablename]
  key = tableids.get(tablename, None)
  if key is not None:
    for row in tableit:
      row["language"] = language
      dest[row[key]] = row
  else:
    dest.extend(tableit)

def get_row_for_id(table, key, canonical=False):
  ''' Retrieves the row for the given id and language. If the key is not found,
      returns None'''
  if canonical and key in language_data['crosslang']:
    key = language_data['crosslang']['canonid']
  return language_data[table].get(key, None)

def get_sql_statements():
  ''' Get sql statements for the global language data. '''
  return language_schema.get_data_sql(language_data)
