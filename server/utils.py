import sqlite3, sys, ctypes

# Load DXR tokenizer for sqlite
_tokenizer_loaded = False
def load_tokenizer():
  global _tokenizer_loaded
  if _tokenizer_loaded:
    return
  try:
    lib = "sqlite-tokenizer/libdxr-code-tokenizer.so"
    ctypes_init_tokenizer = ctypes.CDLL(lib).dxr_code_tokenizer_init
    ctypes_init_tokenizer ()
    _tokenizer_loaded = True
    return True
  except:
    return False

# Regular expression for the sqlite
def _regexp(expr, item):
  reg = re.compile(expr)
  try:
    return reg.search(re.escape (item)) is not None
  except:
    return False

# This makes results a lot more fun!
def _collate_loc(str1, str2):
  parts1 = str1.split(':')
  parts2 = str2.split(':')
  for i in range(1, len(parts1)):
    parts1[i] = int(parts1[i])
  for i in range(2, len(parts2)):
    parts2[i] = int(parts2[i])
  return cmp(parts1, parts2)

# Get database connection for tree
def connect_db(tree):
  load_tokenizer()
  dbname = "../" + tree + "/xref.sqlite"
  try:
    conn = sqlite3.connect(dbname)
    conn.text_factory = str
    conn.create_function("REGEXP", 2, _regexp)
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("SELECT initialize_tokenizer()")
    conn.create_collation("loc", _collate_loc)
    conn.row_factory = sqlite3.Row
    return conn
  except:
    return None

# Log message
def log(msg):
  print >> sys.stderr, "Log: %s" % msg
