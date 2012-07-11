#This trees will be substituted in by dxr-index.py at HTML generation
trees = ${trees}
virtroot = "${virtroot}"

import sqlite3, sys, ctypes

# Read template files neatly
def getTemplateFile(file):
  with open("dxr_server/templates/" + file, "r") as f:
    return f.read()

# Load DXR tokenizer for sqlite
_tokenizer_loaded = False
def load_tokenizer():
  global _tokenizer_loaded
  if _tokenizer_loaded:
    return
  try:
    ctypes_init_tokenizer = ctypes.CDLL("dxr_server/libdxr-code-tokenizer.so").dxr_code_tokenizer_init
    ctypes_init_tokenizer ()
    _tokenizer_loaded = True
  except:
    msg = sys.exc_info()[1] # Python 2/3 compatibility
    print "Could not load tokenizer: %s" % msg
    sys.exit (0)

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
  dbname = tree + "/.dxr_xref/" + tree + ".sqlite"
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
    msg = sys.exc_info()[1] # Python 2/3 compatibility
    print getTemplateFile("dxr-search-header.html") % 'Error'
    print '<h3>Error: Failed to open %s</h3><p>%s' % (dbname, msg)
    sys.exit (0)

