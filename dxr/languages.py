import dxr.plugins

# The following schema is the common global schema, so no matter which plugins
# are used, this schema will always be present. Most tables have a language
# column which indicates the source language that the type is written in.
language_schema = dxr.plugins.Schema({
  # Scope definitions: a scope is anything that is both interesting (i.e., not
  # a namespace) and can contain other objects. The IDs for this scope should be
  # IDs in other tables as well; the table its in can disambiguate which type of
  # scope you're looking at.
  "scopes": [
    ("scopeid", "INTEGER", False),    # An ID for this scope
    ("sname", "VARCHAR(256)", True),  # Name of the scope
    ("sloc", "_location", True),      # Location of the canonical decl
    ("language", "_language", False), # The language of the scope
    ("_key", "scopeid")
  ],
  # Type definitions: anything that defines a type per the relevant specs.
  "types": [
    ("tid", "INTEGER", False),            # Unique ID for the type
    ("scopeid", "INTEGER", False),        # Scope this type is defined in
    ("tname", "VARCHAR(256)", False),     # Simple name of the type
    ("tqualname", "VARCHAR(256)", False), # Fully-qualified name of the type
    ("tloc", "_location", False),         # Location of canonical decl
    ("tkind", "VARCHAR(32)", True),       # Kind of type (e.g., class, union)
    ("language", "_language", False),     # Language of the type
    ("_key", "tid")
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
    ("scopeid", "INTEGER", False),        # Scope defined in
    ("fname", "VARCHAR(256)", False),     # Short name (no args)
    ("fqualname", "VARCHAR(512)", False), # Fully qualified name, excluding args
    ("fargs", "VARCHAR(256)", False),     # Argument string, including parens
    ("ftype", "VARCHAR(256)", False),     # Full return type, as a string
    ("floc", "_location", True),          # Location of definition
    ("modifiers", "VARCHAR(256)", True),  # Modifiers (e.g., private)
    ("language", "_language", False),     # Language of the function
    ("_key", "funcid")
  ],
  # Variables: class, global, local, enum constants; they're all in here
  # Variables are of course not scopes, but for ease of use, they use IDs from
  # the same namespace, no scope will have the same ID as a variable and v.v.
  "variables": [
    ("varid", "INTEGER", False),         # Variable ID
    ("scopeid", "INTEGER", False),       # Scope defined in
    ("vname", "VARCHAR(256)", False),    # Short name
    ("vloc", "_location", True),         # Location of definition
    ("vtype", "VARCHAR(256)", True),     # Full type (including pointer stuff)
    ("modifiers", "VARCHAR(256)", True), # Modifiers for the declaration
    ("language", "_language", False),    # Language of the function
    ("_key", "varid")
  ],
  "crosslang": [
    ("canonid", "INTEGER", False),
    ("otherid", "INTEGER", False),
    ("otherlanguage", "VARCHAR(32)", False),
  ],
})


def get_standard_schema():
  return language_schema.get_create_sql()

def get_sql_statements(lang_name, plugin_blob):
  return language_schema.get_data_sql(plugin_blob, lang_name)
