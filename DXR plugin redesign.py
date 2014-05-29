"""

The build command is responsible for laying down whatever data the indexing
plugins need to do their jobs--possibly nothing if no compiler is involved. The
pre_build hooks of the indexing plugins can help with that: for example, by
setting environment variables.

"""
# Domain constants
# Move up to plugins.py
FILES = 'file'  # A FILES query will be promoted to a LINES query if any other query
           # term triggers a line-based query. Thus, it's important to keep
           # field names and semantics the same between lines and files.
LINES = 'line'


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


class Indexer(dxr.plugins.Indexer):
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
        # We need source_folder, object_folder, temp_folder, and eventually
        # ignore_patterns out of the tree.

    # TODO: Have default implementations in a superclass that return nothing.
    def properties_of_file(self, path):
        """Return an iterable of key-value pairs of data about a file.

        If a list value is returned, it will be merged with lists returned from
        other plugins under equal keys.

        """
        # We go with pairs rather than a map so we can just chain all these
        # together and pass them to a dict constructor: fewer temp vars.

    def properties_of_lines(self, path):
        """Return per-line data for one file.

        Yield an iterable of key-value pairs for each of a file's lines, in
        order by line. The data might be data to search on or data stowed away
        for a later realtime thing to generate refs or regions from.

        If a list value is returned, it will be merged with lists returned from
        other plugins under equal keys.

        """

    # This is probably the place to add property extractors for other kinds of
    # things, like modules, if we ever wanted to support some other view of
    # search results than files or lines, like a D3 diagram of an inheritance
    # hierarchy or call graph. We'd need to come up with some way of looping
    # around those modules to let various plugins contribute. Perhaps we'd
    # introduce another kind of plugin: an enumerator.


class Htmlifier(object):  # a class? It could be a good place to cache things like where the temp folder is between method invocations (while we're still doing static rendering) and the fetched ES document (when we aren't).
    def __init__(self, tree):


    def htmlify_whole_file(path, text)

    def htmlify_line(precomputed_properties)

    # If htmlify_line exists and this file is indexed, call htmlify_line once for each line.
    # Otherwise, call htmlify_whole_file.

    # Use cases:
    # Show a file from ES
    # Show a line from ES
    # Show a file from VCS

    def htmlify(lines, tags_of_lines)
        """Intertwingle """



plugin = DxrPlugin.from_namespace(globals())


# A filter can eventually grow a "kind" attr that says "structural" or "text" or whatever, and we can vary the highlight color or whatever based on that to make identifiers easy to pick out visually.

Index-time:
def mappings()
    """Return a map of {doctype: list of mapping excerpts, ...}."""
def properties_of_file(path)  # for search
def properties_of_lines(path)  # for search
def refs_of_lines(path)
def regions_of_lines(path)
def annotations_of_lines(path)
def links(path)

Realtime:
def refs(path, text)
def refs_of_line(path, line)
def regions(path, text)
def regions_of_line(path, line)
