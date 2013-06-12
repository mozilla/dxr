import ctypes
import os.path
import sys

import dxr.utils  # Load trilite before we load sqlite3. Here be dragons. Reorder these import normally once we merge connect_db and connect_database.
import sqlite3


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
# TODO: Why do both this and connect_database() exist?
def connect_db(tree, instance_path):
    dbname = os.path.join(instance_path, 'trees', tree, '.dxr-xref.sqlite')
    try:
        conn = sqlite3.connect(dbname)
        conn.text_factory = str
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.create_collation("loc", _collate_loc)
        conn.row_factory = sqlite3.Row
        return conn
    except:  # TODO: Die, bare except, die!
        return None

# Log message
def log(msg):
    print >> sys.stderr, "Log: %s" % msg
