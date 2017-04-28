"""Registration and enumeration of DXR plugins"""

from functools import partial
from inspect import isclass, isfunction

from ordereddict import OrderedDict
from pkg_resources import iter_entry_points

from dxr.filters import Filter, LINE
from dxr.indexers import TreeToIndex


class AdHocTreeToIndex(TreeToIndex):
    """A default TreeToIndex created because some plugin provided none"""

    def __init__(self, *args, **kwargs):
        self._file_to_index_class = kwargs.pop('file_to_index_class', None)
        super(AdHocTreeToIndex, self).__init__(*args, **kwargs)

    def file_to_index(self, path, contents):
        if self._file_to_index_class:
            return self._file_to_index_class(
                    path, contents, self.plugin_name, self.tree)


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
    def __init__(self,
                 filters=None,
                 folder_to_index=None,
                 tree_to_index=None,
                 file_to_skim=None,
                 mappings=None,
                 analyzers=None,
                 direct_searchers=None,
                 refs=None,
                 badge_colors=None,
                 config_schema=None):
        """
        :arg filters: A list of filter classes
        :arg folder_to_index: A :class:`FolderToIndex` subclass
        :arg tree_to_index: A :class:`TreeToIndex` subclass
        :arg file_to_skim: A :class:`FileToSkim` subclass
        :arg mappings: Additional Elasticsearch mapping definitions for all the
            plugin's elasticsearch-destined data. A dict with keys for each
            doctype and values reflecting the structure described at
            http://www.elastic.co/guide/en/elasticsearch/reference/current/indices-put-mapping.html.
            Since a FILE-domain query will
            be promoted to a LINE query if any other query term triggers a
            line-based query, it's important to keep field names and semantics
            the same between lines and files. In other words, a LINE mapping
            should generally be a superset of a FILE mapping.
        :arg analyzers: Analyzer, tokenizer, and token and char filter
            definitions for the elasticsearch mappings. A dict with keys
            "analyzer", "tokenizer", etc., following the structure outlined at
            http://www.elastic.co/guide/en/elasticsearch/reference/current/analysis.html.
        :arg direct_searchers: Functions that provide direct search
            capability. Each must take a single query term of type 'text',
            return an elasticsearch filter clause to run against LINEs, and
            have a ``direct_search_priority`` attribute. Filters are tried in
            order of increasing priority. Return None from a direct searcher
            to skip it.

            .. note::

                A more general approach may replace direct search in the
                future.

        :arg refs: An iterable of :class:`~dxr.lines.Ref` subclasses
            supported by this plugin. This is used at request time, to turn
            abreviated ES index data back into HTML.
        :arg badge_colors: Mapping of Filter.lang -> color for menu badges.
        :arg config_schema: A validation schema for this plugin's
            configuration. See https://pypi.python.org/pypi/schema/ for docs.

        ``mappings`` and ``analyzers`` are recursively merged into other
        plugins' mappings and analyzers using the algorithm described at
        :func:`~dxr.utils.deep_update()`. This is mostly intended so you can
        add additional kinds of indexing to fields defined in the core plugin
        using multifields. Don't go too crazy monkeypatching the world.

        """
        self.filters = filters or []
        self.direct_searchers = direct_searchers or []
        self.refs = dict((ref_class.id, ref_class)
                          for ref_class in (refs or []))
        # Someday, these might become lists of indexers or skimmers, and then
        # we can parallelize even better. OTOH, there are probably a LOT of
        # files in any time-consuming tree, so we already have a perfectly
        # effective and easier way to parallelize.
        self.folder_to_index = folder_to_index
        self.tree_to_index = tree_to_index
        self.file_to_skim = file_to_skim
        self.mappings = mappings or {}
        self.analyzers = analyzers or {}
        self.badge_colors = badge_colors or {}
        self.config_schema = config_schema or {}

    @classmethod
    def from_namespace(cls, namespace):
        """Construct a Plugin whose attrs are populated by naming conventions.

        :arg namespace: A namespace from which to pick components

        **Filters** are taken to be any class whose name ends in "Filter" and
        doesn't start with "_".

        **Refs** are taken to be any class whose name ends in "Ref" and
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
                   folder_to_index=namespace.get('FolderToIndex'),
                   tree_to_index=tree_to_index,
                   file_to_skim=namespace.get('FileToSkim'),
                   mappings=namespace.get('mappings'),
                   analyzers=namespace.get('analyzers'),
                   badge_colors=namespace.get('badge_colors'),
                   direct_searchers=direct_searchers_from_namespace(namespace),
                   refs=refs_from_namespace(namespace))

    def __eq__(self, other):
        """Consider instances of the same plugin equal."""
        return self.name == other.name

    def __ne__(self, other):
        return self.name != other.name

    def __hash__(self):
        """Let us put plugins in sets and test for membership."""
        return hash(self.name)

    def __getstate__(self):
        """When pickling, omit the direct searchers.

        We don't use them during the multiprocess indexing phase, so we might
        as well allow ourselves to create direct searchers using function
        factories, whose products are unpickleable.

        """
        copy = self.__dict__.copy()
        copy['direct_searchers'] = []
        return copy

    def __repr__(self):
        return (('<Plugin %s>' % self.name) if hasattr(self, 'name')
                else super(Plugin, self).__repr__())


def filters_from_namespace(namespace):
    """Return the filters which conform to our suggested naming convention:
    ending with "Filter" and not starting with "_".

    :arg namespace: The namespace in which to look for filters

    """
    return [v for k, v in namespace.iteritems() if
            isclass(v) and
            not k.startswith('_') and
            k.endswith('Filter') and
            v is not Filter]


def direct_searchers_from_namespace(namespace):
    """Return a list of the direct search functions defined in a namespace.

    A direct search function is one that has a ``direct_search_priority``
    attribute.

    """
    return [v for v in namespace.itervalues()
            if hasattr(v, 'direct_search_priority') and isfunction(v)]


def refs_from_namespace(namespace):
    """Return a list of :class:`~dxr.lines.Ref` subclasses (or workalikes)
    defined in a namespace, identified by conforming to our naming convention.

    Our convention is to end with "Ref" and not start with "_".

    """
    from dxr.lines import Ref

    # TODO: Consider switching to an isinstance() test so plugin authors have
    # more naming flexibility.
    return [v for k, v in namespace.iteritems() if
            isclass(v) and
            not k.startswith('_') and
            k.endswith('Ref') and
            v is not Ref]


def direct_search(priority, domain=LINE):
    """Mark a function as being a direct search provider.

    :arg priority: A priority to attach to the function. Direct searchers are
        called in order of increasing priority.
    :arg domain: LINE if this searcher searches for individual lines, FILE if
        it searches for entire files

    """
    def decorator(searcher):
        searcher.direct_search_priority = priority
        searcher.domain = domain
        return searcher
    return decorator


_plugin_cache = None
def all_plugins():
    """Return a dict of plugin name -> Plugin for all plugins, including core.

    Plugins are registered via the ``dxr.plugins`` setuptools entry point,
    which may point to either a module (in which case a Plugin will be
    constructed based on the contents of the module namespace) or a Plugin
    object (which will be returned directly). The entry point name is what the
    user types into the config file under ``enabled_plugins``.

    The core plugin, which provides many of DXR's cross-language, built-in
    features, is always the first plugin when iterating over the returned
    dict. This lets other plugins override bits of its elasticsearch mappings
    and analyzers when we're building up the schema.

    """
    global _plugin_cache

    def name_and_plugin(entry_point):
        """Return the name of an entry point and the Plugin it points to."""
        object = entry_point.load()
        plugin = (object if isinstance(object, Plugin) else
                  Plugin.from_namespace(object.__dict__))
        plugin.name = entry_point.name
        return entry_point.name, plugin

    if _plugin_cache is None:
        # Iterating over entrypoints could be kind of expensive, with the FS
        # reads and all.
        _plugin_cache = OrderedDict([('core', core_plugin())])
        _plugin_cache.update(name_and_plugin(point) for point in
                             iter_entry_points('dxr.plugins'))

    return _plugin_cache


def all_plugins_but_core():
    """Do like :func:`all_plugins()`, but don't return the core plugin."""
    ret = all_plugins().copy()
    del ret['core']
    return ret


_core_plugin = None
def core_plugin():
    """Return the core plugin."""
    # This is a function in order to dodge a circular import.
    global _core_plugin
    import dxr.plugins.core

    if _core_plugin is None:
        _core_plugin = Plugin.from_namespace(dxr.plugins.core.__dict__)
        _core_plugin.name = 'core'

    return _core_plugin


def plugins_named(names):
    """Return an iterable of the core plugin, along with Plugins having the
    given names.

    :arg names: An iterable of plugin names

    """
    plugins = all_plugins()
    return (plugins[name] for name in names)
