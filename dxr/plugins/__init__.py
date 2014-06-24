"""The DXR plugin architecture"""

import sys
from os.path import join
import imp
from inspect import isclass

from pkg_resources import iter_entry_points


def indexer_exports():
    """ Indexer files should export these, for use as __all__"""
    return ['pre_process', 'post_process']


def htmlifier_exports():
    """ Htmlifier files should export these, for use as __all__"""
    return ['htmlify', 'load']


def load_indexers(tree):
    """ Load indexers for a given tree """
    # Allow plugins to load from the plugin folder
    sys.path.append(tree.config.plugin_folder)
    plugins = []
    for name in tree.enabled_plugins:
        path = join(tree.config.plugin_folder, name)
        f, mod_path, desc = imp.find_module("indexer", [path])
        plugin = imp.load_module('dxr.plugins.' + name + "_indexer", f, mod_path, desc)
        f.close()
        plugins.append(plugin)
    return plugins


def load_htmlifiers(tree):
    """ Load htmlifiers for a given tree """
    # Allow plugins to load from the plugin folder
    sys.path.append(tree.config.plugin_folder)
    plugins = []
    for name in tree.enabled_plugins:
        path = join(tree.config.plugin_folder, name)
        f, mod_path, desc = imp.find_module("htmlifier", [path])
        plugin = imp.load_module('dxr.plugins.' + name + "_htmlifier", f, mod_path, desc)
        f.close()
        plugins.append(plugin)
    return plugins



## NEW STUFF. Most of the above should go away.

# Domain constants:
FILES = 'file'  # A FILES query will be promoted to a LINES query if any other query
           # term triggers a line-based query. Thus, it's important to keep
           # field names and semantics the same between lines and files.
LINES = 'line'


# This is a concrete example of a Filter. This should move to some kind of
# "core" plugin.
class PathFilter(object):
    """One of these is created for each path: query term and persists through
    the querying and highlighting phases."""

    name = 'path'
    domain = FILES

    def __init__(self, term):
        """This is a good place to parse the term's arg (if it requires further
        parsing) and stash it away on the instance."""

    def filter(self):
        """Return the ES query segment that applies my restrictions to the
        found set of lines.

        Actually, return (a domain constant, the query segment).

        """

    def highlight(self, result):
        """Return a map of result field names to sorted iterables of extents
        that should be highlighted.

        :arg result: A mapping representing properties from a search result,
            whether a file or a line

        """

    # A filter can eventually grow a "kind" attr that says "structural" or
    # "text" or whatever, and we can vary the highlight color or whatever based
    # on that to make identifiers easy to pick out visually.


class TreeToIndex(object):
    """Manager of data extraction from a tree at index time

    A single instance of each TreeToIndex class is used for the entire indexing
    process of a tree.

    Instances must be pickleable so as to make the journey to worker processes.
    You might also want to keep the size down. It takes on the order of 2s for
    a 150MB pickle to make its way across process boundaries, including
    pickling and unpickling time. For this reason, we send the TreeToIndex once
    and then have it index several files before sending it again. The number of
    files per chunk is adjustable via the `something` config option.

    """
    def __init__(self, tree):
        # We need source_folder, object_folder, temp_folder, and maybe
        # ignore_patterns out of the tree.
        self.tree = tree

    def pre_build(self):
        """Hook called before the tree's build command is run

        This is where environment variables are commonly twiddled to activate
        and parametrize compiler plugins which dump analysis data. This is also
        a good place to make a temp folder to dump said data in. You can stash
        away a reference to it on the object so later methods can find it.

        """

    def post_build(self):
        """Hook called after the tree's build command completes

        This is a good place to do any whole-program analysis.

        """

    def file_to_index(self, path, contents):
        """Return a FileToIndex representing a conceptual path in the tree.

        :arg path: A path to the file to index, relative to the tree's source
            folder
        :arg contents: What's in the file: unicode if we managed to guess an
            encoding and decode it, str otherwise

        Return None if there is no indexing to be done on the file.

        Being a method on TreeToIndex, this can easily pass along the location
        of our temp directory or other shared setup artifacts. However, beware
        of passing mutable things; while the FileToIndex can mutate them,
        visibility of those changes will be limited to objects in the same
        worker process. Thus, a TreeToIndex-dwelling dict might be a suitable
        place for a cache, but it's not suitable for data that can't afford to
        evaporate.

        If a plugin omits a TreeToIndex class, :meth:`Plugin.from_namespace()`
        constructs one dynamically. The method implementations of that class
        are inherited from :class:`TreeToIndex`, with one exception: a
        ``file_to_index()`` method is dynamically constructed which returns a
        new instance of whatever ``FileToIndex`` class the plugin defines, if
        any.

        """

    # This is probably the place to add whatever_indexer()s for other kinds of
    # things, like modules, if we ever wanted to support some other view of
    # search results than files or lines, like a D3 diagram of an inheritance
    # hierarchy or call graph. We'd need to come up with some way of looping
    # around those modules to let various plugins contribute. Perhaps we'd
    # introduce another kind of plugin: an enumerator.


class FileToSkim(object):
    """A source of rendering data for a source file generated at request time

    This is appropriate for unindexed files (such as old revisions pulled out
    of a VCS) or for data so large or cheap to produce that it's a bad tradeoff
    to store it in the index. An instance of me is mostly an opportunity for a
    shared cache among my methods.

    """
    def __init__(self, path, contents, tree, file_properties=None, line_properties=None):
        """Construct.

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
        ``links()``, ``refs_by_line()``, etc.

        The default implementation selects only text files.

        """
        return self.contains_text()

    def links(self):
        """Return an iterable of intra-page nav links::

            (sort order, heading, [(icon, title, href), ...])

        """
        return []

    def refs_by_line(self):
        """Yield an ordered list of extents and menus for each line::

            (start, end, (menu, title attribute contents))

        """
        return []

    def regions_by_line(self):
        """Yield an ordered list of extents and CSS classes for each line::

            (start, end, class)

        We'll probably store them in ES as a list of explicit objects, like
        {start: 5, end: 18, class: k}.

        """
        return []

    def annotations_by_line(self):
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
        """Return an iterable of key-value pairs of search data about the file.

        If the framework encounters multiple needles of the same key (whether
        coming from the same plugin or different ones), all unique values will
        be retained.

        """
        # We go with pairs rather than a map so we can just chain all these
        # together and pass them to a dict constructor: fewer temp vars.
        return []

    def needles_by_line(self):
        """Return per-line search data for one file.

        Yield an iterable of key-value pairs for each of a file's lines, in
        order by line. The data might be data to search on or data stowed away
        for a later realtime thing to generate refs or regions from.

        If the framework encounters multiple needles of the same key on the
        same line (whether coming from the same plugin or different ones), all
        unique values will be retained.

        """
        return []

    # Convenience methods:

    def absolute_path(self):
        """Return the absolute path of the file to index."""
        return join(self.tree.source_folder, self.path)


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
        """Construct.

        :arg filters: A list of filter classes
        :arg tree_to_index: A :class:`TreeToIndex` subclass
        :arg file_to_skim: A :class:`FileToSkim` subclass
        :arg mappings: Additional Elasticsearch mapping definitions for all the
            plugin's ES-destined data
        :arg analyzers: Analyzer, tokenizer, and filter definitions for the
            elasticsearch mappings. A dict with keys "analyzer", "tokenizer",
            etc., following the structure outlined at
            http://www.elasticsearch.org/guide/en/elasticsearch/reference/
            current/analysis.html.

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

        Filters are taken to be any class whose name ends in "Filter" and
        doesn't start with "_".

        The tree indexer is assumed to be called "TreeToIndex". If there isn't
        one, one will be constructed which does nothing but delegate to the
        class called ``FileToIndex`` (if there is one) when ``file_to_index()``
        is called on it.

        The file skimmer is assumed to be called "FileToSkim".

        If these rules don't suit you, you can always instantiate a Plugin
        yourself.

        """
        # Grab a tree indexer by name, or make one up:
        tree_to_index = namespace.get('TreeToIndex')
        if not tree_to_index:
            file_to_index_class = namespace.get('FileToIndex')
            class tree_to_index(TreeToIndex):
                """A default TreeToIndex created because none was provided by
                the plugin"""

                if file_to_index_class:
                    def file_to_index(self, path, contents):
                        return file_to_index_class(path, contents, self.tree)

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
            k.endswith('Filter')]


def all_plugins():
    """Return a dict of plugin name -> Plugin for all registered plugins.

    Plugins are registered via the ``dxr.plugins`` setuptools entry point,
    which may point to either a module (in which case a Plugin will be
    constructed based on the contents of the module namespace) or a Plugin
    object (which will be returned directly). The entry point name is what the
    user types into the config file under ``enabled_plugins``.

    """
    def name_and_plugin(entry_point):
        """Return the name of an entry point and the Plugin it points to."""
        object = entry_point.load()
        plugin = (object if isinstance(object, Plugin) else
                  Plugin.from_namespace(object.__dict__))
        return entry_point.name, plugin

    return dict(name_and_plugin(point) for point in
                iter_entry_points('dxr.plugins'))
