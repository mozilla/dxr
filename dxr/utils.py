import sqlite3
import ctypes
import os
import jinja2
import string
from urllib import quote, quote_plus


_trilite_loaded = False
def load_trilite(config):
    """ Load trilite if not loaded before"""
    global _trilite_loaded
    if _trilite_loaded:
        return
    ctypes.CDLL("libtrilite.so").load_trilite_extension()
    _trilite_loaded = True


def connect_database(tree):
    """ Connect to database ensuring that dependencies are built first """
    # Build and load tokenizer if needed
    load_trilite(tree.config)
    # Create connection
    conn = sqlite3.connect(os.path.join(tree.target_folder, ".dxr-xref.sqlite"))
    # Configure connection
    conn.execute("PRAGMA synchronous=off")  # TODO Test performance without this
    conn.execute("PRAGMA page_size=32768")
    # Optimal page should probably be tested, we get a hint from:
    # http://www.sqlite.org/intern-v-extern-blob.html
    conn.text_factory = str
    conn.row_factory  = sqlite3.Row
    return conn


_template_env = None
def load_template_env(temp_folder, template_folder):
    """ Load template environment (lazily) """
    global _template_env
    if not _template_env:
        # Cache folder for jinja2
        tmpl_cache = os.path.join(temp_folder, 'jinja2_cache')
        if not os.path.isdir(tmpl_cache):
            os.mkdir(tmpl_cache)
        # Create jinja2 environment
        _template_env = jinja2.Environment(
                loader          = jinja2.FileSystemLoader(template_folder),
                auto_reload     = False,
                bytecode_cache  = jinja2.FileSystemBytecodeCache(tmpl_cache)
        )
    return _template_env


_next_id = 1
def next_global_id():
    """ Source of unique ids """
    #TODO Please stop using this, it makes distribution and parallelization hard
    # Also it's just stupid!!! When whatever SQL database we use supports this
    global _next_id
    n = _next_id
    _next_id += 1
    return n


def open_log(config_or_tree, name):
    """ Get an open log file given config or tree and name """
    return open(os.path.join(config_or_tree.log_folder, name), 'w')


def non_negative_int(s, default):
    """Parse a string into an int >= 0. If parsing fails or the result is out
    of bounds, return a default."""
    try:
        i = int(s)
        if i >= 0:
            return i
    except (ValueError, TypeError):
        pass
    return default


def search_url(www_root, tree, query, redirect=None):
    """Return the URL to the search endpoint."""
    ret = '%s/%s/search?q=%s' % (www_root,
                                 quote(tree),
                                 # quote_plus needs a string.
                                 quote_plus(query.encode('utf-8')))
    if redirect is not None:
        ret += 'redirect=%s' % ('true' if redirect else 'false')
    return ret
