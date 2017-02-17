from collections import Mapping, defaultdict
from commands import getstatusoutput
from contextlib import contextmanager
from datetime import datetime
from errno import ENOENT
import fnmatch
from functools import wraps
from itertools import izip, imap
from os import chdir, dup, fdopen, getcwd
from os.path import join
from shutil import rmtree
from sys import stdout
from urllib import quote, quote_plus

from flask import current_app

from dxr.exceptions import CommandFailure


DXR_BLUEPRINT = 'dxr_blueprint'


def browse_file_url(tree, path, _anchor=None):
    """Return the URL to the file-browsing endpoint.

    :arg tree: The unicode or str name of the tree whose file to browse
    :arg int _anchor: The line of the file to browse to

    """
    return '%s/%s/source/%s%s' % (current_app.dxr_www_root,
                                  quote(tree.encode('utf-8')),
                                  quote(path.encode('utf-8')),
                                  '' if _anchor is None else '#%i' % _anchor)


def search_url(tree, query):
    """Return the URL to the search endpoint.

    This is equivalent to ``url_for('dxr_blueprint.search', tree=tree.name,
    q=query)``, except it is much faster. We called url_for() 77K times in a
    representative 13KLOC C++ file, and it took 17s. This and
    ``browse_file_url()`` brought it down to 4s.

    :arg tree: The unicode or str name of the tree to search
    :arg query: A unicode or str search query

    """
    return '%s/%s/search?q=%s' % (current_app.dxr_www_root,
                                  quote(tree.encode('utf-8')),
                                  # quote_plus needs a string.
                                  quote_plus(query.encode('utf-8')))


def open_log(folder, name, use_stdout=False):
    """Return a writable file-like object representing a log file.

    :arg folder: The folder to put the log file in
    :arg name: The name of the log file
    :arg use_stdout: If True, return a handle to stdout for verbose output,
        duplicated so it can be closed with impunity.

    """
    if use_stdout:
        return fdopen(dup(stdout.fileno()), 'w')
    return open(join(folder, name), 'w', 1)


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


def format_number(n):
    """Add thousands separators to an integer.

    At the moment, this is hard-coded, but this should be internationalized if
    we ever do that to DXR at large. It is not registered as a template filter
    because it wouldn't work client-side with the AJAX search results.

    """
    try:
        return format(n, ',d')
    except ValueError:  # Give up on 2.6.
        return str(n)


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


def cached(f):
    """Cache the result of a function that takes an iterable of plugins."""
    # TODO: Generalize this into a general memoizer function later if needed.

    cache = {}

    @wraps(f)
    def inner(plugins):
        key = tuple(plugins)
        if key in cache:
            return cache[key]

        result = cache[key] = f(key)
        return result

    return inner


class frozendict(dict):
    """A dict that can be hashed if all its values are hashable

    You shouldn't modify one of these once constructed; it will change the
    hash.

    """
    def __hash__(self):
        items = self.items()
        items.sort()
        return hash(tuple(items))


def if_raises(exception, callable, fallback, *args, **kwargs):
    """Call ``callable`` with ``args`` and ``kwargs``, returning the result.

    If it raises ``exception``, return ``fallback``.

    """
    try:
        return callable(*args, **kwargs)
    except exception:
        return fallback


def run(command):
    """Run a shell command, and return its stdout. On failure, raise
    `CommandFailure`.

    """
    status, output = getstatusoutput(command)
    if status:
        raise CommandFailure(command, status, output)
    return output


def file_text(file_path):
    with open(file_path) as file:
        return file.read()


def bucket(things, key):
    """Return a map of key -> list of things."""
    ret = defaultdict(list)
    for thing in things:
        ret[key(thing)].append(thing)
    return ret


def cumulative_sum(nums):
    """Generate a cumulative sum of nums iterable, at each point yielding
        the sum up to but not including the current value.
    """
    cum_sum = 0
    for n in nums:
        # Note that these two operations are flipped from a traditional
        # cumulative sum, which includes the current value
        yield cum_sum
        cum_sum += n


def build_offset_map(lines):
    """Return a list of byte offsets of the positions of the start of each
    line, where lines is an iterable of strings.
    """
    return list(cumulative_sum(imap(len, lines)))


@contextmanager
def cd(path):
    """Change the working dir on enter, and change it back on exit."""
    old_dir = getcwd()
    chdir(path)
    yield
    chdir(old_dir)


def rmtree_if_exists(folder):
    """Remove a folder if it exists. Otherwise, do nothing."""
    try:
        rmtree(folder)
    except OSError as exc:
        if exc.errno != ENOENT:
            raise


def is_in(needle, haystack):
    """Compare needle against haystack or a list of haystacks.

    If haystack is a list, return whether needle is in haystack. Otherwise,
    return whether needle == haystack.

    """
    return (needle in haystack) if isinstance(haystack, list) else needle == haystack


def without_ending(ending, string):
    """If ``string`` ends with ``ending``, strip it off."""
    return string[:-len(ending)] if string.endswith(ending) else string


def split_content_lines(unicode):
    """Split the content of a recognizably textual file into lines.

    This is a single point of truth for how to do this between skimmers,
    indexers, and other miscellany. At present, line breaks are included in the
    resulting lines. Lines breaks are considered to be \n, \r, or \r\n.

    """
    lines = unicode.splitlines(True)
    # Vertical Tabs, Form Feeds and some other characters are treated as
    # end-of-lines by unicode.splitlines.
    # See https://docs.python.org/2/library/stdtypes.html#unicode.splitlines
    # Since we don't want those characters to be treated as line endings (since
    # clang doesn't treat them so), we take the result and stitch any affected
    # lines back together. We must maintain a consistent notion of line breaks
    # across plugins in order for them to be able to collaborate on an
    # individual file.

    # str.splitlines behaves more as we desire but encoding, calling
    # str.splitlines and then decoding again is slower.

    # Using a frozenset here is faster than using a tuple.
    non_line_endings = frozenset((u"\v", u"\f", u"\x1c", u"\x1d", u"\x1e",
                                  u"\x85", u"\u2028", u"\u2029"))
    def unsplit_some_lines(accum, x):
        if accum and accum[-1] and accum[-1][-1] in non_line_endings:
            accum[-1] += x
        else:
            accum.append(x)
        return accum
    return reduce(unsplit_some_lines, lines, [])


def unicode_for_display(str):
    """Return a unicode representation of a bytestring for showing to humans.

    Different inputs may return the same output.

    """
    return str.decode('utf8', 'replace')
