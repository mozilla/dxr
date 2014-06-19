"""The DXR plugin architecture"""

import os, sys
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


class TreeToIndex(object):
    """Manager of data extraction from a tree at index time

    A single TreeToIndex (for each plugin) is used for the entire build process
    of a tree.

    """
    def __init__(self, tree):
        # We need source_folder, object_folder, temp_folder, and maybe
        # ignore_patterns out of the tree.
        pass

    def pre_build(self):
        """Hook called before the tree's build command is run

        This is where environment variables are commonly twiddled to activate
        and parametrize compiler plugins which dump analysis data. This is also
        a good place to make a temp folder to dump said data in. You can stash
        away a reference to it on the object so later methods can find it.

        """

    def post_build(self):
        """Hook called after the tree's build command completes

        This is a good place to do any whole-program analysis. Plugins are
        responsible for their own parallelism here.

        """

    def file_to_index(self, path, text):
        """Return a FileToIndex representing a conceptual path in the tree.

        :arg path: A tree-relative path to the file to index

        Return None if there is no indexing to be done on the file.

        Being a method on TreeToIndex, this can easily pass the FileToIndex a
        ref to our temp directory or what-have-you.

        """
        # Consider that someday FileToIndex instances may run in parallel, in
        # separate processes. This architecture, with computationally heavy
        # methods like line_refs() being instance methods (and thus
        # unpickleable) might make that tricky. Worst case, we can pass
        # pool.submit() {the (pickleable) instance and the name of the method
        # to call on it} as args to a (pickleable) top-level function that
        # calls that method on that instance.
        return None

    # This is probably the place to add whatever_indexer()s for other kinds of
    # things, like modules, if we ever wanted to support some other view of
    # search results than files or lines, like a D3 diagram of an inheritance
    # hierarchy or call graph. We'd need to come up with some way of looping
    # around those modules to let various plugins contribute. Perhaps we'd
    # introduce another kind of plugin: an enumerator.


class FileViewData(object):
    """Data needed to render a file-view page. Abstract."""

    def links(self):
        """Return an iterable of intra-page nav links."""
        return []

    def refs_by_line(self):
        """Yield an ordered list of extents and menus for each line::

            (start, end, (menu, title attribute contents))

        """
        return []

    def regions_by_line(self):
        """Yield an ordered list of extents for each line.

        We'll probably store them in ES as a list of explicit objects, like
        {start: 5, end: 18, class: k}.

        """
        return []

    def annotations_by_line(self):
        # TODO: Why are these just per line? Shouldn't they return extents like
        # everybody else? We can still show them per line if we want.
        return []


class FileToIndex(FileViewData):
    """A source of search and rendering data about one source file"""

    def __init__(self, path, text='', ):
        """Analyze a file or digest an analysis that happened at compile time.

        Sock it away on an instance var. You can think of this as a per-file
        post-build step. You could do this in a different method, using
        memoization, but this way there's less code and less opportunity for
        mistakes.

        FileToIndex classes of plugins may take whatever constructor args they
        like; it is the responsibility of their ``TreeToIndex.file_to_index()``
        methods to supply them.

        Note that we do not receive the text of the file as an argument. DXR doesn't know whether to read individual files as bytestrings or unicode or what their encodings (if the latter) may be. And the OS file cache should buffer us against really reading the file from disk multiple times. Call the as_unicode() helper method if you want the contents.

    Let's see which of the above and below paragraphs I prefer in the morning.

        :arg contents: The contents of the file as unicode or string. DXR uses
            the tree's ``source_encoding`` hint along with MIME type guessing
            to identify which files are text and decode them appropriately. If
            it succeeds, you get unicode. If not, you get a string, which you
            can interpret as a bytestring to be safe or try to decode yourself
            if you think you know better.

        """
        self.path = path
        self.text = text

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


class FileToSkim(FileViewData):
    """A source of rendering data for a source file generated at request time

    This is appropriate for unindexed files (such as old revisions pulled out
    of a VCS) or for data so large or cheap to produce that it's a bad tradeoff
    to store it in the index. An instance of me is mostly an opportunity for a
    shared cache among my methods.

    """
    def __init__(self, conceptual_path, text, file_properties=None, line_properties=None):
        """Construct.

        :arg conceptual_path: The conceptual path to the file, relative to the
            tree. Such a file might not exist on disk. This is useful mostly as
            a hint for syntax coloring.
        :arg text: The full text of the file

        If the file is indexed, there will also be...

        :arg file_properties: Dict of file-wide needles emitted by the indexer
        :arg line_properties: List of per-line needle dicts emitted by the
            indexer

        """


class Plugin(object):
    """The deployer-visible unit of pluggability

    A Plugin is an indexer, skimmer, and filter set meant to be used together.
    In other words, there is no user-accessible way to subdivide a plugin via
    configuration; there would be no sense running a plugin's filters if the
    indexer that was supposed to extract the requisite data never ran.

    If the deployer should be able to independently enable parts of your
    plugin, consider exposing those as separate plugins.

    """
    def __init__(self, filters=None, tree_to_index=None, file_to_skim=None, mappings=None, analyzers=None):
        """Construct.

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
                    def file_to_index(self, *args, **kwargs):
                        return file_to_index_class(*args, **kwargs)

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
