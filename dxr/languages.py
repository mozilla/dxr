import dxr.schema


# The following schema is the common global schema, so no matter which plugins
# are used, this schema will always be present. Most tables have a language
# column which indicates the source language that the type is written in.
language_schema = dxr.schema.Schema({
    # Scope definitions: a scope is anything that is both interesting (i.e., not
    # a namespace) and can contain other objects. The IDs for this scope should be
    # IDs in other tables as well; the table its in can disambiguate which type of
    # scope you're looking at.
    "files" : [
        ("id", "INTEGER", False),
        ("path", "VARCHAR(1024)", True),
        ("icon", "VARCHAR(64)", True),
        ("encoding", "VARCHAR(16)", False),
        ("_key", "id"),
        ("_index", "path"),               # TODO: Make this a unique index
    ],
    "scopes": [
        ("id", "INTEGER", False),         # An ID for this scope
        ("name", "VARCHAR(256)", True),   # Name of the scope
        ("language", "_language", False), # The language of the scope
        ("_location", True),
        ("_key", "id")
    ],
    # Type definitions: anything that defines a type per the relevant specs.
    "types": [
        ("id", "INTEGER", False),            # Unique ID for the type
        ("scopeid", "INTEGER", True),        # Scope this type is defined in
        ("name", "VARCHAR(256)", False),     # Simple name of the type
        ("qualname", "VARCHAR(256)", False), # Fully-qualified name of the type
        ("kind", "VARCHAR(32)", True),       # Kind of type (e.g., class, union, struct, enum)
        ("language", "_language", True),     # Language of the type
        ("value", "VARCHAR(64)", True),
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_key", "id"),
        ("_fkey", "scopeid", "scopes", "id"),
        ("_index", "qualname"),
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
        ("id", "INTEGER", False),            # Function ID (also in scopes)
        ("declid", "INTEGER", True),         # Function ID of trait method (Rust only)
        ("scopeid", "INTEGER", True),        # Scope defined in
        ("name", "VARCHAR(256)", False),     # Short name (no args)
        ("qualname", "VARCHAR(512)", False), # Fully qualified name, excluding args
        ("args", "VARCHAR(256)", False),     # Argument string, including parens
        ("type", "VARCHAR(256)", False),     # Full return type, as a string
        ("modifiers", "VARCHAR(256)", True),  # Modifiers (e.g., private)
        ("language", "_language", True),     # Language of the function
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_key", "id"),
        ("_fkey", "scopeid", "scopes", "id"),
        ("_fkey", "declid", "functions", "id"),
        ("_index", "qualname"),
    ],
    # Variables: class, global, local, enum constants; they're all in here
    # Variables are of course not scopes, but for ease of use, they use IDs from
    # the same namespace, no scope will have the same ID as a variable and v.v.
    "variables": [
        ("id", "INTEGER", False),           # Variable ID
        ("scopeid", "INTEGER", True),       # Scope defined in
        ("name", "VARCHAR(256)", False),    # Short name
        ("qualname", "VARCHAR(256)", False),# Fully qualified name
        ("type", "VARCHAR(256)", True),     # Full type (including pointer stuff)
        ("modifiers", "VARCHAR(256)", True), # Modifiers for the declaration
        ("language", "_language", True),    # Language of the function
        ("value", "VARCHAR(256)", True),
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_key", "id"),
        ("_fkey", "scopeid", "scopes", "id"),
        ("_index", "qualname"),
    ],
    "crosslang": [
        ("canonid", "INTEGER", False),
        ("otherid", "INTEGER", False),
        ("otherlanguage", "VARCHAR(32)", False),
        ("_key", "otherid")
    ],
})
