"""The DXR plugin architecture"""

from functools import partial, wraps
from os.path import join
from inspect import isclass

from ordereddict import OrderedDict
from pkg_resources import iter_entry_points


# Domain constants:
FILE = 'file'
LINE = 'line'


class Filter(object):
    """A provider of search strategy and highlighting

    Filter classes, which roughly correspond to the items in the Filters
    dropdown menu, tell DXR how to query the data stored in elasticsearch by
    :meth:`~dxr.plugins.FileToIndex.needles` and
    :meth:`~dxr.plugins.FileToIndex.needles_by_line`. An instance is created
    for each query term whose :attr:`name` matches and persists through the
    querying and highlighting phases.

    This is an optional base class that saves code on many filters. It also
    serves to document the filter API.

    :ivar name: The string prefix used in a query term to activate this
        filter. For example, if this were "path", this filter would be
        activated for the query term "path:foo". Multiple filters can be
        registered against a single name; they are ORed together. For example,
        it is good practice for a language plugin to query against a language
        specific needle (like "js-function") but register against the more
        generic "function" here. (This allows us to do language-specific
        queries.)
    :ivar domain: Either LINE or FILE. LINE means this filter returns results
        that point to specific lines of files; FILE means they point to files
        as a whole. Default: LINE.
    :ivar description: A description of this filter for the Filters menu:
        unicode or Markup (in case you want to wrap examples in ``<code>``
        tags). Of filters having the same name, the description of the first
        one encountered will be used. An empty description will hide a filter
        from the menu. This should probably be used only internally, by the
        TextFilter.

    """
    domain = LINE
    description = u''

    def __init__(self, term):
        """This is a good place to parse the term's arg (if it requires further
        parsing) and stash it away on the instance.

        Raise :class:`~dxr.exceptions.BadTerm` to complain to the user: for
        instance, about an unparseable term.

        """
        self._term = term

    def filter(self):
        """Return the ES filter clause that applies my restrictions to the
        found set of lines (or files and folders, if :attr:`domain` is FILES).

        To quietly do no filtration, return ``{}``. This would be suitable for
        ``path:*``, for example.

        To do no filtration and complain to the user about it, raise
        :class:`~dxr.exceptions.BadTerm`.

        We might even make this return a list of filter clauses, for things
        like the RegexFilter which want a bunch of match_phrases and a script.

        """
        raise NotImplementedError

    def highlight_path(self, result):
        """Return a sorted iterable of extents that should be highlighted in
        the ``path`` field of a search result.

        :arg result: A mapping representing properties from a search result,
            whether a file or a line. With access to all the data, you can,
            for example, use the extents from a 'c-function' needle to inform
            the highlighting of the 'content' field.

        """
        return []

    def highlight_content(self, result):
        """Return a sorted iterable of extents that should be highlighted in
        the ``content`` field of a search result.

        :arg result: A mapping representing properties from a search result,
            whether a file or a line. With access to all the data, you can,
            for example, use the extents from a 'c-function' needle to inform
            the highlighting of the 'content' field.

        """
        return []

    # A filter can eventually grow a "kind" attr that says "structural" or
    # "text" or whatever, and we can vary the highlight color or whatever based
    # on that to make identifiers easy to pick out visually.


def negatable(filter_method):
    """Wraps an ES "not" around a ``Filter.filter()`` method iff the term is
    negated.

    """
    @wraps(filter_method)
    def maybe_negate(self):
        positive = filter_method(self)
        return {'not': positive} if self._term['not'] else positive
    return maybe_negate


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
        """Return a dict of environment variables to do the build under.

        This is where environment variables are commonly twiddled to activate
        and parametrize compiler plugins which dump analysis data.

        :arg vars: A dict of the already-set variables. You can make decisions
            based on these.

        You may return a new dict or scribble on ``vars`` and return it.

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
        unique values will be retained using an elasticsearch array.

        """
        return []

    # Convenience methods:

    def absolute_path(self):
        """Return the absolute path of the file to index."""
        return join(self.tree.source_folder, self.path)


class AdHocTreeToIndex(TreeToIndex):
    """A default TreeToIndex created because some plugin provided none"""

    def __init__(self, *args, **kwargs):
        self._file_to_index_class = kwargs.pop('file_to_index_class', None)
        super(AdHocTreeToIndex, self).__init__(*args, **kwargs)

    def file_to_index(self, path, contents):
        if self._file_to_index_class:
            return self._file_to_index_class(path, contents, self.tree)


class Plugin(object):
    """Top-level entrypoint for DXR plugins

    A Plugin is an indexer, skimmer, filter set, and other miscellany meant to
    be used together; it is the deployer-visible unit of pluggability. In other
    words, there is no way to subdivide a plugin via configuration; there would
    be no sense running a plugin's filters if the indexer that was supposed to
    extract the requisite data never ran.

    If the deployer should be able to independently enable parts of your
    plugin, consider exposing those as separate plugins.

    Note that Plugins may be instantiated multiple times; don't assume
    otherwise.

    """
    def __init__(self, filters=None, tree_to_index=None, file_to_skim=None, mappings=None, analyzers=None):
        """
        :arg filters: A list of filter classes
        :arg tree_to_index: A :class:`TreeToIndex` subclass
        :arg file_to_skim: A :class:`FileToSkim` subclass
        :arg mappings: Additional Elasticsearch mapping definitions for all the
            plugin's ES-destined data. A dict with keys for each doctype and
            values reflecting the structure described at
            http://www.elasticsearch.org/guide/en/elasticsearch/reference/
            current/indices-put-mapping.html. Since a FILE-domain query will
            be promoted to a LINE query if any other query term triggers a
            line-based query, it's important to keep field names and semantics
            the same between lines and files. In other words, a LINE mapping
            should generally be a superset of a FILE mapping.
        :arg analyzers: Analyzer, tokenizer, and token and char filter
            definitions for the elasticsearch mappings. A dict with keys
            "analyzer", "tokenizer", etc., following the structure outlined at
            http://www.elasticsearch.org/guide/en/elasticsearch/reference/
            current/analysis.html.

        ``mappings`` and ``analyzers`` are recursively merged into other
        plugins' mappings and analyzers using the algorithm described at
        :func:`~dxr.utils.deep_update()`. This is mostly intended so you can
        add additional kinds of indexing to fields defined in the core plugin
        using multifields. Don't go too crazy monkeypatching the world.

        """
        self.filters = filters or []
        # Someday, these might become lists of indexers or skimmers, and then
        # we can parallelize even better. OTOH, there are probably a LOT of
        # files in any time-consuming tree, so we already have a perfectly
        # effective and easier way to parallelize.
        self.tree_to_index = tree_to_index
        self.file_to_skim = file_to_skim
        self.mappings = mappings or {}
        self.analyzers = analyzers or {}

    @classmethod
    def from_namespace(cls, namespace):
        """Construct a Plugin whose attrs are populated by naming conventions.

        :arg namespace: A namespace from which to pick components

        **Filters** are taken to be any class whose name ends in "Filter" and
        doesn't start with "_".

        The **tree indexer** is assumed to be called "TreeToIndex". If there isn't
        one, one will be constructed which does nothing but delegate to the
        class called ``FileToIndex`` (if there is one) when ``file_to_index()``
        is called on it.

        The **file skimmer** is assumed to be called "FileToSkim".

        **Mappings** are pulled from ``mappings`` attribute and **analyzers**
        from ``analyzers``.

        If these rules don't suit you, you can always instantiate a Plugin
        yourself.

        """
        # Grab a tree indexer by name, or make one up:
        tree_to_index = namespace.get('TreeToIndex')
        if not tree_to_index:
            tree_to_index = partial(
                    AdHocTreeToIndex,
                    file_to_index_class=namespace.get('FileToIndex'))

        return cls(filters=filters_from_namespace(namespace),
                   tree_to_index=tree_to_index,
                   file_to_skim=namespace.get('FileToSkim'),
                   mappings=namespace.get('mappings'),
                   analyzers=namespace.get('analyzers'))  # any other settings needed?


def filters_from_namespace(namespace):
    """Return the filters which conform to our suggested naming convention.

    :arg namespace: The namespace in which to look for filters

    """
    return [v for k, v in namespace.iteritems() if
            isclass(v) and
            not k.startswith('_') and
            k.endswith('Filter') and
            v is not Filter]


def all_plugins():
    """Return a dict of plugin name -> Plugin for all registered plugins.

    Plugins are registered via the ``dxr.plugins`` setuptools entry point,
    which may point to either a module (in which case a Plugin will be
    constructed based on the contents of the module namespace) or a Plugin
    object (which will be returned directly). The entry point name is what the
    user types into the config file under ``enabled_plugins``.

    The core plugin, which provides many of DXR's cross-language, built-in
    features, is always the first plugin when iterating over the returned
    dict. This lets other plugins override bits of its ES mappings and
    analyzers.

    """
    import dxr.plugins.core

    def name_and_plugin(entry_point):
        """Return the name of an entry point and the Plugin it points to."""
        object = entry_point.load()
        plugin = (object if isinstance(object, Plugin) else
                  Plugin.from_namespace(object.__dict__))
        return entry_point.name, plugin

    ret = OrderedDict()
    ret['core'] = Plugin.from_namespace(dxr.plugins.core.__dict__)
    ret.update(name_and_plugin(point) for point in
               iter_entry_points('dxr.plugins'))
    return ret
