"""C and C++ plugin, using a clang compiler plugin"""

from dxr.plugins import Plugin, filters_from_namespace
from dxr.plugins.clang import direct, filters
from dxr.plugins.clang.indexers import TreeToIndex, mappings


plugin = Plugin(filters=filters_from_namespace(filters.__dict__),
                tree_to_index=TreeToIndex,
                mappings=mappings,
                direct_searchers=direct.searchers)
