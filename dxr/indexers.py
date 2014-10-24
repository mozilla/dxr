"""Base classes and convenience functions for writing indexers and skimmers"""

from collections import namedtuple
from operator import itemgetter

from funcy import group_by, decorator, imapcat


class TreeToIndex(object):
    """A TreeToIndex performs build environment setup and teardown and serves
    as a repository for scratch data that should persist across an entire
    indexing run.

    Instances must be pickleable so as to make the journey to worker processes.
    You might also want to keep the size down. It takes on the order of 2s for
    a 150MB pickle to make its way across process boundaries, including
    pickling and unpickling time. For this reason, we send the TreeToIndex once
    and then have it index several files before sending it again.

    """
    def __init__(self, tree):
        """
        :arg tree: The configuration of the tree to index: a TreeConfig

        """
        # We need source_folder, object_folder, temp_folder, and maybe
        # ignore_patterns out of the tree.
        self.tree = tree

    def environment(self, vars):
        """Return environment variables to add to the build environment.

        This is where the environment is commonly twiddled to activate and
        parametrize compiler plugins which dump analysis data.

        :arg vars: A dict of the already-set variables. You can make decisions
            based on these.

        You may return a new dict or scribble on ``vars`` and return it. In
        either case, the returned dict is merged into those from other plugins,
        with later plugins taking precedence in case of conflicting keys.

        """
        return vars

    def pre_build(self):
        """Hook called before the tree's build command is run

        This is a good place to make a temp folder to dump said data in. You
        can stash away a reference to it on me so later methods can find it.

        """

    def post_build(self):
        """Hook called after the tree's build command completes

        This is a good place to do any whole-program analysis, storing it on
        me or on disk.

        """

    def file_to_index(self, path, contents):
        """Return an object that provides data about a given file.

        Return an object conforming to the interface of :class:`FileToIndex`,
        generally a subclass of it.

        :arg path: A path to the file to index, relative to the tree's source
            folder
        :arg contents: What's in the file: unicode if we managed to guess an
            encoding and decode it, str otherwise

        Return None if there is no indexing to do on the file.

        Being a method on TreeToIndex, this can easily pass along the location
        of a temp directory or other shared setup artifacts. However, beware
        of passing mutable things; while the FileToIndex can mutate them,
        visibility of those changes will be limited to objects in the same
        worker process. Thus, a TreeToIndex-dwelling dict might be a suitable
        place for a cache but unsuitable for data that can't evaporate.

        If a plugin omits a TreeToIndex class, :meth:`Plugin.from_namespace()`
        constructs one dynamically. The method implementations of that class
        are inherited from this class, with one exception: a
        ``file_to_index()`` method is dynamically constructed which returns a
        new instance of the ``FileToIndex`` class the plugin defines, if any.

        """

    # This is probably the place to add whatever_indexer()s for other kinds of
    # things, like modules, if we ever wanted to support some other view of
    # search results than files or lines, like a D3 diagram of an inheritance
    # hierarchy or call graph. We'd need to come up with some way of looping
    # around those modules to let various plugins contribute. Perhaps we'd
    # introduce another kind of plugin: an enumerator.


class FileToSkim(object):
    """A source of rendering data about a file, generated at request time

    This is appropriate for unindexed files (such as old revisions pulled out
    of a VCS) or for data so large or cheap to produce that it's a bad tradeoff
    to store it in the index. An instance of me is mostly an opportunity for a
    shared cache among my methods.

    """
    def __init__(self, path, contents, tree, file_properties=None, line_properties=None):
        """
        :arg path: The conceptual path to the file, relative to the tree's
            source folder. Such a file might not exist on disk. This is useful
            mostly as a hint for syntax coloring.
        :arg contents: What's in the file: unicode if we knew or successfully
            guessed an encoding, str otherwise. Don't return any by-line data
            for strs; the framework won't have succeeded in breaking up the
            file by line for display, so there will be no useful UI for those
            data to support. In fact, most skimmers won't be be able to do
            anything useful with strs at all. For unicode, split the file into
            lines using universal newlines (``unicode.splitlines()`` with no
            params); that's what the rest of the framework expects.
        :arg tree: The :class:`~dxr.config.TreeConfig` of the tree to which
            the file belongs

        If the file is indexed, there will also be...

        :arg file_properties: Dict of file-wide needles emitted by the indexer
        :arg line_properties: List of per-line needle dicts emitted by the
            indexer

        """
        self.path = path
        self.contents = contents
        self.tree = tree
        self.file_properties = file_properties or {}
        self.line_properties = line_properties  # TODO: not clear what the default here should be. repeat([])?

    def is_interesting(self):
        """Return whether it's worthwhile to examine this file.

        For example, if this class knows about how to analyze JS files, return
        True only if ``self.path.endswith('.js')``. If something falsy is
        returned, the framework won't call data-producing methods like
        ``links()``, ``refs()``, etc.

        The default implementation selects only text files.

        """
        return self.contains_text()

    def links(self):
        """Return an iterable of intra-page nav links::

            (sort order, heading, [(icon, title, href), ...])

        """
        return []

    def refs(self):
        """Provide cross references for various spans of text, accessed
        through a context menu.

        Yield an ordered list of extents and menu items for each line::

            (start, end, (menu, title))

        ``start`` and ``end`` are the bounds of a slice of a Unicode string
        holding the contents of the file. (``refs()`` will not be called for
        binary files.)

        ``title`` is the contents of the <a> tag's title attribute. (The first
        one wins.)

        ``menu`` is a mapping representing an item of the context menu::

            {'html': 'description',
             'title': 'longer description',
             'href': 'URL',
             'icon': 'extensionless name of a PNG from the icons folder'}

        """
        return []

    def regions(self):
        """Yield instructions for syntax coloring and other inline formatting
        of code.

        Yield an ordered list of extents and CSS classes for each line::

            (start, end, class)

        ``start`` and ``end`` are the bounds of a slice of a Unicode string
        holding the contents of the file. (``regions()`` will not be called
        for binary files.)

        We'll probably store them in ES as a list of explicit objects, like
        {start: 5, end: 18, class: k}.

        """
        return []

    def annotations_by_line(self):
        """Yield extra user-readable information about each line, hidden by
        default: compiler warnings that occurred there, for example.

        Yield a list of annotation maps for each line::

            {'title': ..., 'class': ..., 'style': ...}

        """
        # TODO: Why are these just per line? Shouldn't they return extents like
        # everybody else? We can still show them per line if we want.
        return []

    # Convenience methods:

    def contains_text(self):
        """Return whether this file can be decoded and divided into lines as
        text.

        This may come in handy as a component of your own
        :meth:`is_interesting()` methods.

        """
        return isinstance(self.contents, unicode)


class FileToIndex(FileToSkim):
    """A source of search and rendering data about one source file"""

    def __init__(self, path, contents, tree):
        """Analyze a file or digest an analysis that happened at compile time.

        :arg path: A path to the file to index, relative to the tree's source
            folder
        :arg contents: What's in the file: unicode if we managed to guess at an
            encoding and decode it, str otherwise. Don't return any by-line
            data for strs; the framework won't have succeeded in breaking up
            the file by line for display, so there will be no useful UI for
            those data to support. Think more along the lines of returning
            EXIF data to search by for a JPEG. For unicode, split the file into
            lines using universal newlines (``unicode.splitlines()`` with no
            params); that's what the rest of the framework expects.
        :arg tree: The :class:`~dxr.config.TreeConfig` of the tree to which
            the file belongs

        Initialization-time analysis results may be socked away on an instance
        var. You can think of this constructor as a per-file post-build step.
        You could do this in a different method, using memoization, but doing
        it here makes for less code and less opportunity for error.

        FileToIndex classes of plugins may take whatever constructor args they
        like; it is the responsibility of their
        :meth:`TreeToIndex.file_to_index()` methods to supply them. However,
        the ``path`` and ``contents`` instance vars should be initialized and
        have the above semantics, or a lot of the provided convenience methods
        and default implementations will break.

        """
        # We receive the file contents from the outside for two reasons: (1) so
        # we don't repeatedly redo the encoding guessing (which involves
        # iterating over potentially the whole file looking for nulls) and (2)
        # for symmetry with FileToSkim, so we can share many method
        # implementations.
        super(FileToIndex, self).__init__(path, contents, tree)

    def needles(self):
        """Return an iterable of key-value pairs of search data about the file
        as a whole: for example, modification date or file size.

        Each pair becomes an elasticsearch property and its value. If the
        framework encounters multiple needles of the same key (whether coming
        from the same plugin or different ones), all unique values will be
        retained using an elasticsearch array.

        """
        # We go with pairs rather than a map so we can just chain all these
        # together and pass them to a dict constructor: fewer temp vars.
        return []

    def needles_by_line(self):
        """Return per-line search data for one file: for example, markers that
        indicate a function called "foo" is defined on a certain line.

        Yield an iterable of key-value pairs for each of a file's lines, one
        iterable per line, in order. The data might be data to search on or
        data stowed away for a later realtime thing to generate refs or
        regions from. In any case, each pair becomes an elasticsearch property
        and its value.

        If the framework encounters multiple needles of the same key on the
        same line (whether coming from the same plugin or different ones), all
        unique values will be retained using an elasticsearch array. Values
        may be dicts, in which case common keys get merged by
        :func:`~dxr.utils.append_update()`.

        """
        return []

    # Convenience methods:

    def absolute_path(self):
        """Return the absolute path of the file to index."""
        return join(self.tree.source_folder, self.path)


# Conveniences:


Extent = namedtuple('Extent', ['start', 'end'])  # 0-based
# Note that if offset is a Maybe Int, if not present it's None
Position = namedtuple('Position', ['offset', 'row', 'col'])  # offset & col 0-based, row 1-based
Call = namedtuple('Call', ['callee', 'caller', 'calltype'])


class FuncSig(namedtuple('FuncSig', ['inputs', 'output'])):
    def __str__(self):
        return '{0} -> {1}'.format(
            tuple(self.inputs), self.output).replace("'", '').replace('"', '')


@decorator
def unsparsify(call):
    """Transform a sparse needle list [(key, val, span:Extent)] into the
    line-by-line format needles_by_line expects: [[(key, val)]].

    """
    return group_needles(by_line(call()))


def group_needles(line_needles):
    """Group line needles by line, and return a list of needles for each line,
    up to the last line with any needles::

        [(a, 1), (b, 4), (c, 4)] -> [[a], [], [], [b, c]]

    """
    # Jam all the needles of a file into a hash by line number:
    line_map = group_by(itemgetter(1), line_needles)  # {line: needles}
    last_line = max(line_map.iterkeys()) + 1 if line_map else 1

    # Pull out the needles for each line, stripping off the line number
    # elements of the tuples and producing a blank list for missing lines.
    # (The defaultdict returned from group_by takes care of the latter.)
    return [[pair for (pair, _) in line_map[line_num]]
            for line_num in xrange(1, last_line)]


def by_line(span_needles):
    """Transform [(_, span:Extent)] into [(_, line:int)].

    Converts spans to lines. The resulting iter will have len' >= len.

    """
    return ((key_object_pair(*kv_start_end), line_number) for
            kv_start_end, line_number in imapcat(span_to_lines, span_needles))


def key_object_pair((k, v), start, end):
    """Transform a key/value pair, along with start and end columns, to a
    key/multi-propertied-object pair that can be stored in ES and then used
    to support searching and highlighting.

    """
    return k, {'value': v, 'start': start, 'end': end}


def span_to_lines((kv, span)):
    """Expand ((k, v), span:Extent) into [(((k, v), line_span), line:int)].

    line_span has shape: (col1, col2)

    """
    if span.end.row == span.start.row:
        yield (kv, span.start.col, span.end.col), span.start.row

    elif span.end.row < span.start.row:
        raise ValueError("end.row < start.row")

    else:
        # TODO: There are a lot of Nones used as slice bounds below. Do we
        # ever translate them back into char offsets? If not, does the
        # highlighter or anything else choke on them?
        yield (kv, span.start.col, None), span.start.row

        # Really wish we could use yield from
        for row in xrange(span.start.row + 1, span.end.row):
            yield (kv, 0, None), row

        yield (kv, 0, span.end.col), span.end.row




def split_into_lines(triples):
    """Split a bunch of (key, mapping, extent) triples into more triples
    than those, with each one contained in a line.

    """
    def _split_one((key, mapping, extent)):
        """Split a single triple into one or more, each spanning at most one
        line.

        """
        if extent.end.row == extent.start.row:
            yield key, mapping, extent
        elif extent.end.row < extent.start.row:
            raise ValueError('Bad Extent: end.row < start.row')
        else:
            # TODO: There are a lot of Nones used as slice bounds below. Do we
            # ever translate them back into char offsets? If not, does the
            # highlighter or anything else choke on them?
            yield key, mapping, Extent(Position(offset=None,
                                                row=extent.start.row,
                                                col=extent.start.col),
                                       Position(offset=None,
                                                row=extent.start.row,
                                                col=None))

            # Really wish we could use yield from
            for row in xrange(extent.start.row + 1, extent.end.row):
                yield key, mapping, Extent(Position(offset=None,
                                                    row=row,
                                                    col=0),
                                           Position(offset=None,
                                                    row=row,
                                                    col=None))

            yield key, mapping, Extent(Position(offset=None,
                                                row=extent.end.row,
                                                col=0),
                                       Position(offset=None,
                                                row=extent.end.row,
                                                col=extent.end.col))

    return imapcat(_split_one, triples)


def with_start_and_end(triples):
    """Add 'start' and 'end' column keys to the value mappings of one-line
    triples, and yield them back.

    """
    for key, mapping, extent in triples:
        mapping['start'] = extent.start.col
        mapping['end'] = extent.end.col
        yield key, mapping, extent


def iterable_per_line(triples):
    """Yield iterables of (key, value mapping), one for each line."""
    # Jam all the triples of a file into a hash by line number:
    line_map = group_by(lambda (k, v, extent): extent.start.row, triples)  # {line: triples}
    last_line = max(line_map.iterkeys()) + 1 if line_map else 1

    # Pull out the needles for each line, stripping off the extents and
    # producing a blank list for missing lines. (The defaultdict returned from
    # group_by takes care of the latter.)
    return [[(k, v) for (k, v, e) in line_map[line_num]]
            for line_num in xrange(1, last_line)]

    # If this has to be generic so we can use it on annotations_by_line as well, pass in a key function that extracts the line number and maybe another that constructs the return value.
