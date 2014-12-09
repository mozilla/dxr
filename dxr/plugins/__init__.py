"""Registration and enumeration of DXR plugins"""

from functools import partial
from inspect import isclass, isfunction
from os.path import join

from ordereddict import OrderedDict
from pkg_resources import iter_entry_points

from dxr.filters import Filter
from dxr.indexers import TreeToIndex


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
    def __init__(self, filters=None, tree_to_index=None, file_to_skim=None, mappings=None, analyzers=None, direct_searchers=None):
        """
        :arg filters: A list of filter classes
        :arg tree_to_index: A :class:`TreeToIndex` subclass
        :arg file_to_skim: A :class:`FileToSkim` subclass
        :arg mappings: Additional Elasticsearch mapping definitions for all the
            plugin's elasticsearch-destined data. A dict with keys for each
            doctype and values reflecting the structure described at
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
        :arg direct_searchers: Functions that provide direct search
            capability. Each must take a single query term of type 'text',
            return an elasticsearch filter clause to run against LINEs, and
            have a ``direct_search_priority`` attribute. Filters are tried in
            order of increasing priority. Return None from a direct searcher
            to skip it.

            .. note::

                A more general approach may replace direct search in the
                future.

        ``mappings`` and ``analyzers`` are recursively merged into other
        plugins' mappings and analyzers using the algorithm described at
        :func:`~dxr.utils.deep_update()`. This is mostly intended so you can
        add additional kinds of indexing to fields defined in the core plugin
        using multifields. Don't go too crazy monkeypatching the world.

        """
        self.filters = filters or []
        self.direct_searchers = direct_searchers or []
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
                   analyzers=namespace.get('analyzers'),
                   direct_searchers=direct_searchers_from_namespace(namespace))


def filters_from_namespace(namespace):
    """Return the filters which conform to our suggested naming convention.

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


def direct_search(priority):
    """Mark a function as being a direct search provider.

    :arg priority: A priority to attach to the function. Direct searchers are
        called in order of increasing priority.

    """
    def decorator(searcher):
        searcher.direct_search_priority = priority
        return searcher
    return decorator


def all_plugins():
    """Return a dict of plugin name -> Plugin for all registered plugins.

    Plugins are registered via the ``dxr.plugins`` setuptools entry point,
    which may point to either a module (in which case a Plugin will be
    constructed based on the contents of the module namespace) or a Plugin
    object (which will be returned directly). The entry point name is what the
    user types into the config file under ``enabled_plugins``.

    The core plugin, which provides many of DXR's cross-language, built-in
    features, is always the first plugin when iterating over the returned
    dict. This lets other plugins override bits of its elasticsearch mappings
    and analyzers.

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
