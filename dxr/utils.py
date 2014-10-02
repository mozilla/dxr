from collections import Mapping
from datetime import datetime
import fnmatch
import os
from os import dup, fdopen
from os.path import join
from itertools import izip
from sys import stdout
from urllib import quote, quote_plus


TEMPLATE_DIR = 'static/templates'


def open_log(config_or_tree, name, use_stdout=False):
    """Return a writable file-like object representing a log file.

    :arg config_or_tree: a Config or Tree object which tells us which folder to
        put the log file in
    :arg name: The name of the log file
    :arg use_stdout: If True, return a handle to stdout for verbose output,
        duplicated so it can be closed with impunity.

    """
    if use_stdout:
        return fdopen(dup(stdout.fileno()), 'w')
    return open(join(config_or_tree.log_folder, name), 'w', 1)


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


# TODO: Obsolete this and browse_url in favor of Flask's url_for.
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


def deep_update(dest, source):
    """Overlay two dictionaries recursively.

    Overwrite keys that hold non-mapping values. Raise TypeError if ``dest``
    and ``source`` disagree about which values are mappings.

    """
    for k, v in source.iteritems():
        source_is_mapping = isinstance(v, Mapping)
        if k in dest and source_is_mapping != isinstance(dest[k], Mapping):
            raise TypeError("Can't merge value %r into %r for key %r." %
                            (dest[k], v, k))
        dest[k] = (deep_update(dest.get(k, {}), v) if source_is_mapping
                   else source[k])
    return dest


def append_update(mapping, pairs):
    """Merge key-value pairs into a mapping, preserving conflicting ones by
    expanding values into lists.

    Return the updated mapping.

    :arg mapping: The mapping into which to merge the new pairs. All values
        must be lists.
    :arg pairs: An iterable of key-value pairs

    """
    for k, v in pairs:
        mapping.setdefault(k, []).append(v)
    return mapping


def append_update_by_line(mappings, pairses):
    """:func:`append_update()` each group of pairs into its parallel
    ``mappings`` element.

    Return the updated ``mappings``.

    :arg mappings: A list of mappings the same length as ``pairses``
    :arg pairses: An iterable of iterables of pairs to :func:`append_update()`
        into ``mappings``, each into its parallel mapping

    """
    for mapping, pairs in izip(mappings, pairses):
        append_update(mapping, pairs)
    return mappings


def append_by_line(dest_lists, list_per_line):
    """Given a list and parallel iterable ``list_per_line``, merge the
    element of the second into the element of the first."""
    for dest_list, source_list in izip(dest_lists, list_per_line):
        dest_list.extend(source_list)
    return dest_lists


def decode_es_datetime(es_datetime):
    """Turn an elasticsearch datetime into a datetime object."""
    try:
        return datetime.strptime(es_datetime, '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        # For newer ES versions
        return datetime.strptime(es_datetime, '%Y-%m-%dT%H:%M:%S.%f')


_FNMATCH_TRANSLATE_SUFFIX_LEN = len('\Z(?ms)')
def glob_to_regex(glob):
    """Return a regex equivalent to a shell-style glob.

    Don't include the regex flags and \\Z at the end like fnmatch.translate(),
    because we don't parse flags and we don't want to pin to the end.

    """
    return fnmatch.translate(glob)[:-_FNMATCH_TRANSLATE_SUFFIX_LEN]
