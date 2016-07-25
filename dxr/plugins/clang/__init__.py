"""C and C++ analysis using a clang compiler plugin

This plugin handles structural analysis of C++ code by building the project
under clang while interposing a custom compiler plugin that dumps out
structural data to CSV files during compilation. This is then pulled into
elasticsearch as a post-processing phase.

"""
from dxr.plugins import Plugin, filters_from_namespace, refs_from_namespace
from dxr.plugins.clang import direct, filters, menus
from dxr.plugins.clang.indexers import TreeToIndex, mappings


plugin = Plugin(filters=filters_from_namespace(filters.__dict__),
                tree_to_index=TreeToIndex,
                mappings=mappings,
                badge_colors={'c': '#F4FAAA'},
                direct_searchers=direct.searchers,
                refs=refs_from_namespace(menus.__dict__))
