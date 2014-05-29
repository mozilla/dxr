"""

The build command is responsible for laying down whatever data the indexing
plugins need to do their jobs--possibly nothing if no compiler is involved. The
constructors of the indexing plugins can help with that: for example, by
setting environment variables.

"""
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


class TreeIndexer(dxr.plugins.TreeIndexer):
    """Manager of data extraction that happens at index time

    A single instance of this is used for the entire build process of a tree.

    """
    def __init__(self, tree):
        """The constructor is called before the tree's build command is run.

        You can use it as a pre-build hook. This is where environment variables
        are commonly twiddled to activate and parametrize compiler plugins
        which dump analysis data. This is also a good place to make a temp
        folder if needed. You can stash away a reference to it on the object so
        later methods can find it.

        """
        # We need source_folder, object_folder, temp_folder, and maybe
        # ignore_patterns out of the tree.

    def mappings(self):
        """Return a map of {doctype: list of mapping excerpts, ...}."""

    def file_indexer(self, path):
        """Return an object that's in charge of indexing the given file."""
        return FileIndexer(path, self.the_temp_stash_or_whatever)


class FileIndexer(dxr.plugins.FileIndexer)
    """A representation of a file that can spit out the indexed bits a plugin
    wants."""

    def __init__(self, path):
        """Analyze a file or digest an analysis that happened at compile time.

        Sock it away on an instance var.

        """
        # Or you could do this later with caching, but this way you can't screw
        # it up.

    # TODO: Have default implementations in a superclass that return nothing.
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
        """Yield an ordered list of extents for each line."""

    def line_regions(self):
        """Yield an ordered list of extents for each line."""

    def line_annotations(self):

    # This is probably the place to add property extractors for other kinds of
    # things, like modules, if we ever wanted to support some other view of
    # search results than files or lines, like a D3 diagram of an inheritance
    # hierarchy or call graph. We'd need to come up with some way of looping
    # around those modules to let various plugins contribute. Perhaps we'd
    # introduce another kind of plugin: an enumerator.


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
        :arg doc_properties: A list of per-line properties emitted by the
            indexer, if the document is indexed

        """

    def refs(self):
        """Yield an ordered list of extents for each line."""

    def regions(self):
        """Yield an ordered list of extents for each line."""

    def links(self):
        """You could slap together a quick and dirty list of functions here if
        the file wasn't indexed.."""


# Use cases:
# Show a file from ES
# Show a line from ES
# Show a file from VCS


plugin = DxrPlugin.from_namespace(globals())
