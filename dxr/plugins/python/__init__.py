"""Python plugin, using the ast and tokenize standard library modules"""

from dxr.config import AbsPath
from dxr.plugins import filters_from_namespace, refs_from_namespace, Plugin
from dxr.plugins.python import filters, menus
from dxr.plugins.python.indexers import mappings, TreeToIndex


plugin = Plugin(
    filters=filters_from_namespace(filters.__dict__),
    tree_to_index=TreeToIndex,
    mappings=mappings,
    badge_colors={'py': '#ECE6FD'},
    refs=refs_from_namespace(menus.__dict__),
    config_schema = {
        'python_path': AbsPath
    }
)
