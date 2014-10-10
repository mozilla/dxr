import csv, cgi
import json
import dxr.plugins
import dxr.schema
import os, sys
import re, urllib
from dxr.languages import language_schema
csv.field_size_limit(sys.maxsize)

PLUGIN_NAME   = 'clang'

__all__ = dxr.plugins.indexer_exports()


def pre_process(tree, env):
    # Setup environment variables for inspecting clang as runtime
    # We'll store all the havested metadata in the plugins temporary folder.
    temp_folder   = os.path.join(tree.temp_folder, 'plugins', PLUGIN_NAME)
    plugin_folder = os.path.join(tree.config.plugin_folder, PLUGIN_NAME)
    flags = [
        '-load', os.path.join(plugin_folder, 'libclang-index-plugin.so'),
        '-add-plugin', 'dxr-index',
        '-plugin-arg-dxr-index', tree.source_folder
    ]
    flags_str = ""
    for flag in flags:
        flags_str += ' -Xclang ' + flag
    env['CC']   = "clang %s"   % flags_str
    env['CXX']  = "clang++ %s" % flags_str
    env['DXR_CC'] = env['CC']
    env['DXR_CXX'] = env['CXX']
    env['DXR_CLANG_FLAGS'] = flags_str
    env['DXR_CXX_CLANG_OBJECT_FOLDER']  = tree.object_folder
    env['DXR_CXX_CLANG_TEMP_FOLDER']    = temp_folder


def post_process(tree, conn):
    print "cxx-clang post-processing:"
    print " - Adding tables"
    conn.executescript(schema.get_create_sql())

    print " - Processing files"
    temp_folder = os.path.join(tree.temp_folder, 'plugins', PLUGIN_NAME)
    for f in os.listdir(temp_folder):
        csv_path = os.path.join(temp_folder, f)
        dump_indexer_output(conn, csv_path)

    fixup_scope(conn)
    
    print " - Generating callgraph"
    generate_callgraph(conn)
    
    print " - Generating inheritance graph"
    generate_inheritance(conn)

    print " - Updating definitions"
    update_defids(conn)

    print " - Updating references"
    update_refs(conn)

    print " - Committing changes"
    conn.commit()



schema = dxr.schema.Schema({
    # Typedef information in the tables
    "typedefs": [
        ("id", "INTEGER", False),              # The typedef's id
        ("name", "VARCHAR(256)", False),       # Simple name of the typedef
        ("qualname", "VARCHAR(256)", False),   # Fully-qualified name of the typedef
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_key", "id"),
        ("_index", "qualname"),
    ],
    # Namespaces
    "namespaces": [
        ("id", "INTEGER", False),              # The namespaces's id
        ("name", "VARCHAR(256)", False),       # Simple name of the namespace
        ("qualname", "VARCHAR(256)", False),   # Fully-qualified name of the namespace
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_key", "id"),
        ("_index", "qualname"),
    ],
    # References to namespaces
    "namespace_refs": [
        ("refid", "INTEGER", True),      # ID of the namespace being referenced
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_location", True, 'referenced'),
        ("_fkey", "refid", "namespaces", "id"),
        ("_index", "refid"),
    ],
    # Namespace aliases
    "namespace_aliases": [
        ("id", "INTEGER", False),              # The namespace alias's id
        ("name", "VARCHAR(256)", False),       # Simple name of the namespace alias
        ("qualname", "VARCHAR(256)", False),   # Fully-qualified name of the namespace alias
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_key", "id"),
        ("_index", "qualname"),
    ],
    # References to namespace aliases
    "namespace_alias_refs": [
        ("refid", "INTEGER", True),      # ID of the namespace alias being referenced
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_location", True, 'referenced'),
        ("_fkey", "refid", "namespace_aliases", "id"),
        ("_index", "refid"),
    ],
    # References to functions
    "function_refs": [
        ("refid", "INTEGER", True),      # ID of the function being referenced
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_location", True, 'referenced'),
        ("_fkey", "refid", "functions", "id"),
        ("_index", "refid"),
    ],
    # References to macros
    "macro_refs": [
        ("refid", "INTEGER", True),      # ID of the macro being referenced
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_location", True, 'referenced'),
        ("_fkey", "refid", "macros", "id"),
        ("_index", "refid"),
    ],
    # References to types
    "type_refs": [
        ("refid", "INTEGER", True),      # ID of the type being referenced
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_location", True, 'referenced'),
        ("_fkey", "refid", "types", "id"),
        ("_index", "refid"),
    ],
    # References to typedefs
    "typedef_refs": [
        ("refid", "INTEGER", True),      # ID of the typedef being referenced
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_location", True, 'referenced'),
        ("_fkey", "refid", "typedefs", "id"),
        ("_index", "refid"),
    ],
    # References to variables
    "variable_refs": [
        ("refid", "INTEGER", True),      # ID of the variable being referenced
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_location", True, 'referenced'),
        ("_fkey", "refid", "variables", "id"),
        ("_index", "refid"),
    ],
    # Warnings found while compiling
    "warnings": [
        ("msg", "VARCHAR(256)", False), # Text of the warning
        ("opt", "VARCHAR(64)", True),   # option controlling this warning (-Wxxx)
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
    ],
    # Declaration/definition mapping for functions
    "function_decldef": [
        ("defid", "INTEGER", True),    # ID of the definition instance
        ("_location", True),
        ("_location", True, 'definition'),
        # Extents of the declaration
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_fkey", "defid", "functions", "id"),
        ("_index", "defid"),
    ],
    # Declaration/definition mapping for types
    "type_decldef": [
        ("defid", "INTEGER", True),    # ID of the definition instance
        ("_location", True),
        ("_location", True, 'definition'),
        # Extents of the declaration
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_fkey", "defid", "types", "id"),
        ("_index", "defid"),
    ],
    # Declaration/definition mapping for variables
    "variable_decldef": [
        ("defid", "INTEGER", True),    # ID of the definition instance
        ("_location", True),
        ("_location", True, 'definition'),
        # Extents of the declaration
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_fkey", "defid", "variables", "id"),
        ("_index", "defid"),
    ],
    # Macros: this is a table of all of the macros we come across in the code.
    "macros": [
        ("id", "INTEGER", False),        # The macro id, for references
        ("name", "VARCHAR(256)", False), # The name of the macro
        ("args", "VARCHAR(256)", True),  # The args of the macro (if any)
        ("text", "TEXT", True),          # The macro contents
        ("extent_start", "INTEGER", True),
        ("extent_end", "INTEGER", True),
        ("_location", True),
        ("_key", "id"),
    ],
    # #include and #import directives
    # If we can't resolve the target to a file in the tree, we just omit the
    # row.
    "includes": [
        ("id", "INTEGER", False),  # surrogate key
        ("file_id", "INTEGER", False),  # file where the #include directive is
        ("extent_start", "INTEGER", False),
        ("extent_end", "INTEGER", False),
        ("target_id", "INTEGER", False),  # file pointed to by the #include
        ("_key", "id"),  # so it autoincrements
        ("_fkey", "file_id", "files", "id"),
        ("_fkey", "target_id", "files", "id"),
        ("_index", "file_id"),
    ],
    # The following two tables are combined to form the callgraph implementation.
    # In essence, the callgraph can be viewed as a kind of hypergraph, where the
    # edges go from functions to sets of functions and variables. For use in the
    # database, we are making some big assumptions: the targetid is going to be
    # either a function or variable (the direct thing we called); if the function
    # is virtual or the target is a variable, we use the targets table to identify
    # what the possible implementations could be.
    "callers": [
        ("callerid", "INTEGER", False), # The function in which the call occurs
        ("targetid", "INTEGER", False), # The target of the call
        ("_key", "callerid", "targetid"),
        ("_fkey", "callerid", "functions", "id")
    ],
    "targets": [
        ("targetid", "INTEGER", False), # The target of the call
        ("funcid", "INTEGER", False),   # One of the functions in the target set
        ("_key", "targetid", "funcid"),
        ("_fkey", "funcid", "functions", "id"),
        ("_index", "funcid"),
    ]
})


file_cache = {}
decl_master = {}
inheritance = {}
calls = {}
overrides = {}

def getFileID(conn, path):
    global file_cache

    file_id = file_cache.get(path, False)

    if file_id is not False:
        return file_id

    cur = conn.cursor()
    row = cur.execute("SELECT id FROM files where path=?", (path,)).fetchone()
    file_id = None
    if row:
        file_id = row[0]
    file_cache[path] = file_id
    return file_id

def splitLoc(conn, value):
    arr = value.split(':')
    return (getFileID(conn, arr[0]), int(arr[1]), int(arr[2]))

def fixupEntryPath(args, file_key, conn, prefix=None):
    value = args[file_key]
    loc = splitLoc(conn, value)

    if prefix is not None:
        prefix = prefix + "_"
    else:
        prefix = ''

    args[prefix + 'file_id'] = loc[0]
    args[prefix + 'file_line'] = loc[1]
    args[prefix + 'file_col'] = loc[2]
    return loc[0] is not None

def fixupExtent(args, extents_key='extent'):
    if extents_key not in args:
        # We use -1 instead of NULL because in UNIQUE constraints SQLite
        # treats NULLs as distinct from all other values including other
        # NULLs and this would lead to duplicate rows
        args['extent_start'] = -1
        args['extent_end'] = -1
        return

    value = args[extents_key]
    arr = value.split(':')

    args['extent_start'] = int(arr[0])
    args['extent_end'] = int(arr[1])
    del args[extents_key]

def getScope(args, conn):
    row = conn.execute("SELECT id FROM scopes WHERE file_id=? AND file_line=? AND file_col=?",
                                          (args['file_id'], args['file_line'], args['file_col'])).fetchone()

    if row is not None:
        return row[0]

    return None

def addScope(args, conn, name, id):
    scope = {}
    scope['name'] = args[name]
    scope['id'] = args[id]
    scope['file_id'] = args['file_id']
    scope['file_line'] = args['file_line']
    scope['file_col'] = args['file_col']
    scope['language'] = 'native'

    stmt = language_schema.get_insert_sql('scopes', scope)
    conn.execute(stmt[0], stmt[1])

def handleScope(args, conn, canonicalize=False):
    scope = {}

    if 'scopename' not in args:
        return

    scope['name'] = args['scopename']
    scope['loc'] = args['scopeloc']
    scope['language'] = 'native'
    if not fixupEntryPath(scope, 'loc', conn):
        return None

    if canonicalize is True:
        decl = canonicalize_decl(scope['name'], scope['file_id'], scope['file_line'], scope['file_col'])
        scope['file_id'], scope['file_line'], scope['file_col'] = decl[1], decl[2], decl[3]

    scopeid = getScope(scope, conn)

    if scopeid is None:
        scope['id'] = scopeid = dxr.utils.next_global_id()
        stmt = language_schema.get_insert_sql('scopes', scope)
        conn.execute(stmt[0], stmt[1])

    if scopeid is not None:
        args['scopeid'] = scopeid

def _truncate(s, length=32):
    if len(s) <= length:
        return s
    return s[:length - 3] + '...'

def process_decldef(args, conn):
    if 'kind' not in args:
        return None

    # Store declaration map basics on memory
    qualname, defloc, declloc = args['qualname'], args['defloc'], args['declloc']
    defid, defline, defcol = splitLoc(conn, args['defloc'])
    declid, declline, declcol = splitLoc (conn, args['declloc'])
    if defid is None or declid is None:
        return None

    # FIXME: should kind be included in this mapping?
    decl_master[(qualname, declid, declline, declcol)] = (defid, defline, defcol)
    decl_master[(qualname, defid, defline, defcol)] = (defid, defline, defcol)

    if not fixupEntryPath(args, 'declloc', conn):
        return None
    if not fixupEntryPath(args, 'defloc', conn, 'definition'):
        return None
    fixupExtent(args, 'extent')
    
    return schema.get_insert_sql(args['kind'] + '_decldef', args)

def process_type(args, conn):
    if not fixupEntryPath(args, 'loc', conn):
        return None

    # Scope might have been previously added to satisfy other process_* call
    scopeid = getScope(args, conn)

    if scopeid is not None:
        args['id'] = scopeid
    else:
        args['id'] = dxr.utils.next_global_id()
        addScope(args, conn, 'name', 'id')

    handleScope(args, conn)
    fixupExtent(args, 'extent')

    return language_schema.get_insert_sql('types', args)

def process_typedef(args, conn):
    args['id'] = dxr.utils.next_global_id()
    if not fixupEntryPath(args, 'loc', conn):
        return None
    fixupExtent(args, 'extent')
#  handleScope(args, conn)
    return schema.get_insert_sql('typedefs', args)

def process_function(args, conn):
    if not fixupEntryPath(args, 'loc', conn):
        return None
    scopeid = getScope(args, conn)

    if scopeid is not None:
        args['id'] = scopeid
    else:
        args['id'] = dxr.utils.next_global_id()
        addScope(args, conn, 'name', 'id')

    if 'overridename' in args:
        overrides[args['id']] = (args['overridename'], args['overrideloc'])

    handleScope(args, conn)
    fixupExtent(args, 'extent')
    return language_schema.get_insert_sql('functions', args)

def process_impl(args, conn):
    inheritance[args['tbname'], args['tbloc'], args['tcname'], args['tcloc']] = args
    return None

def process_variable(args, conn):
    args['id'] = dxr.utils.next_global_id()
    if 'value' in args:
        args['value'] = _truncate(args['value'])
    if not fixupEntryPath(args, 'loc', conn):
        return None
    handleScope(args, conn)
    fixupExtent(args, 'extent')
    return language_schema.get_insert_sql('variables', args)

def process_ref(args, conn):
    if 'extent' not in args:
        return None
    if 'kind' not in args:
        return None

    if not fixupEntryPath(args, 'loc', conn):
        return None
    if not fixupEntryPath(args, 'declloc', conn, 'referenced'):
        return None
    fixupExtent(args, 'extent')

    return schema.get_insert_sql(args['kind'] + '_refs', args)

def process_warning(args, conn):
    if not fixupEntryPath(args, 'loc', conn):
        return None
    fixupExtent(args, 'extent')
    return schema.get_insert_sql('warnings', args)

def process_macro(args, conn):
    args['id'] = dxr.utils.next_global_id()
    if 'text' in args:
        args['text'] = args['text'].replace("\\\n", "\n").strip()
        args['text'] = _truncate(args['text'])
    if not fixupEntryPath(args, 'loc', conn):
        return None
    fixupExtent(args, 'extent')
    return schema.get_insert_sql('macros', args)

def process_call(args, conn):
    if 'callername' in args:
        calls[args['callername'], args['callerloc'],
                    args['calleename'], args['calleeloc']] = args
    else:
        calls[args['calleename'], args['calleeloc']] = args

    return None

def process_namespace(args, conn):
    if not fixupEntryPath(args, 'loc', conn):
        return None
    args['id'] = dxr.utils.next_global_id()
    fixupExtent(args, 'extent')
    return schema.get_insert_sql('namespaces', args)

def process_namespace_alias(args, conn):
    if not fixupEntryPath(args, 'loc', conn):
        return None
    args['id'] = dxr.utils.next_global_id()
    fixupExtent(args, 'extent')
    return schema.get_insert_sql('namespace_aliases', args)

def process_include(args, conn):
    """Turn an "include" line from a CSV into a row in the "includes" table."""
    fixupExtent(args)
    # If the ignore_patterns in the config file keep an #included file from
    # making it into the files table, just pretend that include doesn't exist.
    # Thus, IGNORE.
    return ('INSERT OR IGNORE INTO includes '
            '(file_id, extent_start, extent_end, target_id) '
            'VALUES ((SELECT id FROM files WHERE path=?), ?, ?, '
                    '(SELECT id FROM files WHERE path=?))',
            (args['source_path'], args['extent_start'], args['extent_end'], args['target_path']))

def load_indexer_output(fname):
    f = open(fname, "rb")
    try:
        parsed_iter = csv.reader(f)
        for line in parsed_iter:
            # Our first column is the type that we're reading; the others are
            # just an args array to be passed in.
            argobj = {}
            for i in range(1, len(line), 2):
                argobj[line[i]] = line[i + 1]
            globals()['process_' + line[0]](argobj)
    except Exception:
        print fname, line
        raise
    finally:
        f.close()

def dump_indexer_output(conn, fname):
    f = open(fname, 'r')
    limit = 0

    try:
        parsed_iter = csv.reader(f)
        for line in parsed_iter:
            args = {}
            # Our first column is the type that we're reading, the others are just
            # a key/value pairs array to be passed in
            for i in range(1, len(line), 2):
                args[line[i]] = line[i + 1]

            stmt = globals()['process_' + line[0]](args, conn)

            if stmt is None:
                continue

            if isinstance(stmt, list):
                for elem in list:
                    conn.execute(elem[0], elem[1])
            elif isinstance(stmt, tuple):
                try:
                    conn.execute(stmt[0], stmt[1])
                except Exception:
                    print line
                    print stmt
                    raise
            else:
                conn.execute(stmt)

            limit = limit + 1

            if limit > 10000:
                limit = 0
                conn.commit()
    except IndexError:
        raise
    finally:
        f.close()

def canonicalize_decl(name, id, line, col):
    value = decl_master.get((name, id, line, col), None)

    if value is None:
        return (name, id, line, col)
    else:
        return (name, value[0], value[1], value[2])

def recanon_decl(name, loc):
    decl_master[name, loc] = loc
    return (name, loc)

def fixup_scope(conn):
    conn.execute ("UPDATE types SET scopeid = (SELECT id FROM scopes WHERE " +
                                "scopes.file_id = types.file_id AND scopes.file_line = types.file_line " +
                                "AND scopes.file_col = types.file_col) WHERE scopeid IS NULL")
    conn.execute ("UPDATE functions SET scopeid = (SELECT id from scopes where " +
                                "scopes.file_id = functions.file_id AND scopes.file_line = functions.file_line " +
                                "AND scopes.file_col = functions.file_col) WHERE scopeid IS NULL")
    conn.execute ("UPDATE variables SET scopeid = (SELECT id from scopes where " +
                                "scopes.file_id = variables.file_id AND scopes.file_line = variables.file_line " +
                                "AND scopes.file_col = variables.file_col) WHERE scopeid IS NULL")


def build_inherits(base, child, direct):
    db = { 'tbase': base, 'tderived': child }
    if direct is not None:
        db['inhtype'] = direct
    return db

def _chunked_fetchall(cursor, chunk_size=100):
    """Drop in replacement for fetchall designed to be tuned by 'chunking'.

    Return a generator yielding lists of chunk_size rows.

    """
    rows = cursor.fetchmany(chunk_size)
    while rows:
        for row in rows:
            yield row
        rows = cursor.fetchmany(chunk_size)


def generate_inheritance(conn):
    childMap, parentMap = {}, {}
    types = {}

    cursor = conn.execute("SELECT qualname, file_id, file_line, file_col, id from types")
    for row in _chunked_fetchall(cursor):
        types[(row[0], row[1], row[2], row[3])] = row[4]

    for infoKey in inheritance:
        info = inheritance[infoKey]
        try:
            base_loc = splitLoc(conn, info['tbloc'])
            child_loc = splitLoc(conn, info['tcloc'])
            if base_loc[0] is None or child_loc[0] is None:
                continue

            base = types[canonicalize_decl(info['tbname'], base_loc[0], base_loc[1], base_loc[2])]
            child = types[canonicalize_decl(info['tcname'], child_loc[0], child_loc[1], child_loc[2])]
        except KeyError:
            continue

        conn.execute("INSERT OR IGNORE INTO impl(tbase, tderived, inhtype) VALUES (?, ?, ?)",
                                  (base, child, info.get('access', '')))

        # Get all known relations
        subs = childMap.setdefault(child, [])
        supers = parentMap.setdefault(base, [])
        # Use this information
        for sub in subs:
            conn.execute("INSERT OR IGNORE INTO impl(tbase, tderived) VALUES (?, ?)",
                                      (base, sub))
            parentMap[sub].append(base)
        for sup in supers:
            conn.execute("INSERT OR IGNORE INTO impl(tbase, tderived) VALUES (?, ?)",
                                      (sup, child))
            childMap[sup].append(child)

        # Carry through these relations
        newsubs = childMap.setdefault(base, [])
        newsubs.append(child)
        newsubs.extend(subs)
        newsupers = parentMap.setdefault(child, [])
        newsupers.append(base)
        newsupers.extend(supers)


def generate_callgraph(conn):
    global calls
    functions = {}
    variables = {}
    callgraph = []

    cursor = conn.execute("SELECT qualname, file_id, file_line, file_col, id FROM functions")
    for row in _chunked_fetchall(cursor):
        functions[(row[0], row[1], row[2], row[3])] = row[4]
    
    cursor = conn.execute("SELECT name, file_id, file_line, file_col, id FROM variables")
    for row in _chunked_fetchall(cursor):
        variables[(row[0], row[1], row[2], row[3])] = row[4]

    # Generate callers table
    for call in calls.values():
        if 'callername' in call:
            caller_loc = splitLoc(conn, call['callerloc'])
            if caller_loc[0] is None:
                continue
            source = canonicalize_decl(call['callername'], caller_loc[0], caller_loc[1], caller_loc[2])
            call['callerid'] = functions.get(source)

            if call['callerid'] is None:
                continue
        else:
            call['callerid'] = 0

        target_loc = splitLoc(conn, call['calleeloc'])
        if target_loc[0] is None:
            continue
        target = canonicalize_decl(call['calleename'], target_loc[0], target_loc[1], target_loc[2])
        targetid = functions.get(target)

        if targetid is None:
            targetid = variables.get(target)

        if targetid is not None:
            call['targetid'] = targetid
            callgraph.append(call)

    del variables

    # Generate targets table
    overridemap = {}

    for func, funcid in functions.iteritems():
        override = overrides.get(funcid)

        if override is None:
            continue

        override_loc = splitLoc(conn, override[1])
        if override_loc[0] is None:
            continue
        base = canonicalize_decl(override[0], override_loc[0], override_loc[1], override_loc[2])
        basekey = functions.get(base)

        if basekey is None:
            continue

        overridemap.setdefault(basekey, set()).add(funcid)

    rescan = [x for x in overridemap]
    while len(rescan) > 0:
        base = rescan.pop(0)
        childs = overridemap[base]
        prev = len(childs)
        temp = childs.union(*(overridemap.get(sub, []) for sub in childs))
        childs.update(temp)
        if len(childs) != prev:
            rescan.append(base)

    for base, childs in overridemap.iteritems():
        conn.execute("INSERT OR IGNORE INTO targets (targetid, funcid) VALUES (?, ?)",
                                  (-base, base));

        for child in childs:
            conn.execute("INSERT OR IGNORE INTO targets (targetid, funcid) VALUES (?, ?)",
                                      (-base, child));

    for call in callgraph:
        if call['calltype'] == 'virtual':
            targetid = call['targetid']
            call['targetid'] = -targetid
            if targetid not in overridemap:
                overridemap[targetid] = set()
                conn.execute("INSERT OR IGNORE INTO targets (targetid, funcid) VALUES (?, ?)",
                                          (-targetid, targetid));
        conn.execute("INSERT OR IGNORE INTO callers (callerid, targetid) VALUES (?, ?)",
                                    (call['callerid'], call['targetid']))


def update_defids(conn):
    sql = """
        UPDATE type_decldef SET defid = (
              SELECT id
                FROM types AS def
               WHERE def.file_id   = definition_file_id
                 AND def.file_line = definition_file_line
                 AND def.file_col  = definition_file_col
        )"""
    conn.execute(sql)
    sql = """
        UPDATE function_decldef SET defid = (
              SELECT id
                FROM functions AS def
               WHERE def.file_id   = definition_file_id
                 AND def.file_line = definition_file_line
                 AND def.file_col  = definition_file_col
        )"""
    conn.execute(sql)
    sql = """
        UPDATE variable_decldef SET defid = (
              SELECT id
                FROM variables AS def
               WHERE def.file_id   = definition_file_id
                 AND def.file_line = definition_file_line
                 AND def.file_col  = definition_file_col
        )"""
    conn.execute(sql)


def update_refs(conn):
    # References to declarations
    sql = """
        UPDATE type_refs SET refid = (
                SELECT defid
                  FROM type_decldef AS decl
                 WHERE decl.file_id   = referenced_file_id
                   AND decl.file_line = referenced_file_line
                   AND decl.file_col  = referenced_file_col
        ) WHERE refid IS NULL"""
    conn.execute(sql)
    sql = """
        UPDATE function_refs SET refid = (
                SELECT defid
                  FROM function_decldef AS decl
                 WHERE decl.file_id   = referenced_file_id
                   AND decl.file_line = referenced_file_line
                   AND decl.file_col  = referenced_file_col
        ) WHERE refid IS NULL"""
    conn.execute(sql)
    sql = """
        UPDATE variable_refs SET refid = (
                SELECT defid
                  FROM variable_decldef AS decl
                 WHERE decl.file_id   = referenced_file_id
                   AND decl.file_line = referenced_file_line
                   AND decl.file_col  = referenced_file_col
        ) WHERE refid IS NULL"""
    conn.execute(sql)

    # References to definitions
    sql = """
        UPDATE macro_refs SET refid = (
                SELECT id
                  FROM macros AS def
                 WHERE def.file_id    = referenced_file_id
                   AND def.file_line  = referenced_file_line
                   AND def.file_col   = referenced_file_col
        ) WHERE refid IS NULL"""
    conn.execute(sql)
    sql = """
        UPDATE type_refs SET refid = (
                SELECT id
                  FROM types AS def
                 WHERE def.file_id    = referenced_file_id
                   AND def.file_line  = referenced_file_line
                   AND def.file_col   = referenced_file_col
        ) WHERE refid IS NULL"""
    conn.execute(sql)
    sql = """
        UPDATE typedef_refs SET refid = (
                SELECT id
                  FROM typedefs AS def
                 WHERE def.file_id    = referenced_file_id
                   AND def.file_line  = referenced_file_line
                   AND def.file_col   = referenced_file_col
        ) WHERE refid IS NULL"""
    conn.execute(sql)
    sql = """
        UPDATE function_refs SET refid = (
                SELECT id
                  FROM functions AS def
                 WHERE def.file_id    = referenced_file_id
                   AND def.file_line  = referenced_file_line
                   AND def.file_col   = referenced_file_col
        ) WHERE refid IS NULL"""
    conn.execute(sql)
    sql = """
        UPDATE variable_refs SET refid = (
                SELECT id
                  FROM variables AS def
                 WHERE def.file_id    = referenced_file_id
                   AND def.file_line  = referenced_file_line
                   AND def.file_col   = referenced_file_col
        ) WHERE refid IS NULL"""
    conn.execute(sql)
    sql = """
        UPDATE namespace_refs SET refid = (
                SELECT id
                  FROM namespaces AS def
                 WHERE def.file_id    = referenced_file_id
                   AND def.file_line  = referenced_file_line
                   AND def.file_col   = referenced_file_col
        ) WHERE refid IS NULL"""
    conn.execute(sql)
    sql = """
        UPDATE namespace_alias_refs SET refid = (
                SELECT id
                  FROM namespace_aliases AS def
                 WHERE def.file_id    = referenced_file_id
                   AND def.file_line  = referenced_file_line
                   AND def.file_col   = referenced_file_col
        ) WHERE refid IS NULL"""
    conn.execute(sql)
