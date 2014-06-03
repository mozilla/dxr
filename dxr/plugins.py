import os, sys
import imp


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
        path = os.path.join(tree.config.plugin_folder, name)
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
        path = os.path.join(tree.config.plugin_folder, name)
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


class TreeIndexer(object):
    """Manager of data extraction that happens at index time

    A single instance of this is used for the entire build process of a tree.

    """
    def __init__(self, tree):
        # We need source_folder, object_folder, temp_folder, and maybe
        # ignore_patterns out of the tree.

    def pre_build(self):
        """Call this before the tree's build command is run.

        This is where environment variables are commonly twiddled to activate
        and parametrize compiler plugins which dump analysis data. This is also
        a good place to make a temp folder to dump said data in. You can stash
        away a reference to it on the object so later methods can find it.

        """

    # def post_build? What if there's whole-program stuff to do after the
    # build? One could fire it off the first time file_indexer() is called, but
    # that's mysterious.

    def mappings(self):
        """Return a map of {doctype: list of mapping excerpts, ...}."""

    def file_indexer(self, path):
        """Return a FileIndexer for the conceptual path ``path`` in the tree.

        Being a method on TreeIndexer, this can easily pass the FileIndexer a
        ref to our temp directory or what-have-you.

        """
        return FileIndexer(path, self.the_temp_stash_or_whatever)

    # This is probably the place to add whatever_indexer()s for other kinds of
    # things, like modules, if we ever wanted to support some other view of
    # search results than files or lines, like a D3 diagram of an inheritance
    # hierarchy or call graph. We'd need to come up with some way of looping
    # around those modules to let various plugins contribute. Perhaps we'd
    # introduce another kind of plugin: an enumerator.


class FileIndexer(object):
    """A source of search and rendering data about one source file"""

    def __init__(self, path):
        """Analyze a file or digest an analysis that happened at compile time.

        Sock it away on an instance var. You can think of this as a per-file
        post-build step.

        """
        # Or you could do this later with caching, but this way you can't screw
        # it up.

    # TODO: Have default implementation return nothing.
    def morsels(self):
        """Return an iterable of key-value pairs of search data about the file.

        If a list value is returned, it will be merged with lists returned from
        other plugins under equal keys.

        """
        # We go with pairs rather than a map so we can just chain all these
        # together and pass them to a dict constructor: fewer temp vars.

    def links(self):

    def line_morsels(self):
        """Return per-line search data for one file.

        Yield an iterable of key-value pairs for each of a file's lines, in
        order by line. The data might be data to search on or data stowed away
        for a later realtime thing to generate refs or regions from.

        If a list value is returned, it will be merged with lists returned from
        other plugins under equal keys.

        """

    def line_refs(self):
        """Yield an ordered list of extents and menus for each line."""

    def line_regions(self):
        """Yield an ordered list of extents for each line."""

    def line_annotations(self):
        # TODO: Why are these just per line? Shouldn't they return extents like
        # everybody else? We can still show them per line if we want.


class FileSkimmer(dxr.plugins.FileSkimmer):
    """An opportunity for a shared cache among methods which quickly analyze a
    file at request time"""

    def __init__(self, path, text, doc_properties=None, line_properties=None):
        """Construct.

        :arg path: The conceptual path to the file, relative to the tree. Such
            a file might not exist on disk. This is useful mostly as a hint for
            syntax coloring.
        :arg text: The full text of the file
        :arg doc_properties: Document-wide properties emitted by the indexer,
            if the document is indexed
        :arg line_properties: A list of per-line properties emitted by the
            indexer, if the document is indexed

        """

    def refs(self):
        """Yield an ordered list of extents and menus for each line."""

    def regions(self):
        """Yield an ordered list of extents for each line."""

    def links(self):
        """You could slap together a quick and dirty list of functions here if
        the file wasn't indexed.."""


class DxrPlugin(object):
    def __init__(self, filters=None, tree_indexer=None, file_skimmer=None):
        self.filters = filters or []
        self.tree_indexer = tree_indexer
        self.file_skimmer = file_skimmer

    @classmethod
    def from_namespace(namespace):
        """Construct a DxrPlugin whose attrs are populated by typical naming
        and subclassing conventions.

        :arg namespace: A namespace from which to pick components

        Filters are taken to be any class whose name ends in "Filter" and
        doesn't start with "_".

        The indexer is assumed to be called "Indexer".

        If these rules don't suit you, you can always instantiate a DxrPlugin
        yourself (and think about refactoring this so separately expose the
        magic rules you *do* find useful.

        """
        return DxrPlugin(filters=[v for k, v in namespace.iteritems() if
                                  isclass(v) and
                                  not k.startswith('_') and
                                  k.endswith('Filter')],
                         tree_indexer=namespace.get('TreeIndexer'),
                         file_skimmer=namespace.get('FileSkimmer'))


# Use cases:
# Show a file from ES
# Show a line from ES
# Show a file from VCS
