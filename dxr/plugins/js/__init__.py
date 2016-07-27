"""JS plugin: analyze Javascript files by building a symbol map on parse by
esprima.
"""

from dxr.plugins import Plugin, filters_from_namespace, refs_from_namespace
from dxr.filters import LINE
from dxr.indexers import QUALIFIED_LINE_NEEDLE
from dxr.plugins.js.indexers import TreeToIndex
from dxr.plugins.js.refs import PLUGIN_NAME
from dxr.plugins.js import refs, filters


mappings = {
    LINE: {
        'properties': {
            PLUGIN_NAME + '_prop': QUALIFIED_LINE_NEEDLE,
            PLUGIN_NAME + '_var': QUALIFIED_LINE_NEEDLE,
            PLUGIN_NAME + '_prop_ref': QUALIFIED_LINE_NEEDLE,
            PLUGIN_NAME + '_var_ref': QUALIFIED_LINE_NEEDLE
        }
    }
}


plugin = Plugin(
    tree_to_index=TreeToIndex,
    mappings=mappings,
    badge_colors={'js': '#D0FCF8'},
    refs=refs_from_namespace(refs.__dict__),
    filters=filters_from_namespace(filters.__dict__),
)
