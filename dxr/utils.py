import ctypes

# Load the trilite plugin.
#
# If you ``import sqlite3`` before doing this, it's likely that the system
# version of sqlite will be loaded, and then trilite, if built against a
# different version, will fail to load. If you're having trouble getting
# trilite to load, make sure you're not importing sqlite3 beforehand. Afterward
# is fine.
ctypes.CDLL('libtrilite.so').load_trilite_extension()

import os
from os import dup
from os.path import join
import jinja2
import sqlite3
import string
from sys import stdout
from urllib import quote, quote_plus


TEMPLATE_DIR = 'static/templates'


def connect_database(tree):
    """Connect to database ensuring that dependencies are built first"""
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
def load_template_env(temp_folder, dxr_root):
    """Load template environment (lazily)"""
    global _template_env
    if not _template_env:
        # Cache folder for jinja2
        tmpl_cache = os.path.join(temp_folder, 'jinja2_cache')
        if not os.path.isdir(tmpl_cache):
            os.mkdir(tmpl_cache)
        # Create jinja2 environment
        _template_env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(
                        join(dxr_root, TEMPLATE_DIR)),
                auto_reload=False,
                bytecode_cache=jinja2.FileSystemBytecodeCache(tmpl_cache)
        )
    return _template_env


_next_id = 1
def next_global_id():
    """Source of unique ids"""
    #TODO Please stop using this, it makes distribution and parallelization hard
    # Also it's just stupid!!! When whatever SQL database we use supports this
    global _next_id
    n = _next_id
    _next_id += 1
    return n


def open_log(config_or_tree, name, use_stdout=False):
    """Return a writable file-like object representing a log file.

    :arg config_or_tree: a Config or Tree object which tells us which folder to
        put the log file in
    :arg name: The name of the log file
    :arg use_stdout: If True, return a handle to stdout for verbose output,
        duplicated so it can be closed with impunity.

    """
    if use_stdout:
        return os.fdopen(dup(stdout.fileno()), 'w')
    return open(os.path.join(config_or_tree.log_folder, name), 'w', 1)


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


def search_url(www_root, tree, query, **query_string_params):
    """Return the URL to the search endpoint."""
    ret = '%s/%s/search?q=%s' % (www_root,
                                 quote(tree),
                                 # quote_plus needs a string.
                                 quote_plus(query.encode('utf-8')))
    for key, value in query_string_params.iteritems():
        if value is not None:
            ret += '&%s=%s' % (key, ('true' if value else 'false'))
    return ret


def browse_url(tree, www_root, path):
    """Return a URL that will redirect to a given path in a given tree."""
    return quote_plus('{www_root}/{tree}/parallel/{path}'.format(
                          www_root=www_root,
                          tree=tree,
                          path=path),
                      '/')
    # TODO: Stop punting on path components that actually have '/' in them
    # once we define a consistent handling of escapes in build.py. Same for
    # search_url().
