from functools import partial

from dxr.filters import LINE
import dxr.indexers
from dxr.indexers import iterable_per_line, with_start_and_end, split_into_lines, QUALIFIED_LINE_NEEDLE
from dxr.plugins import Plugin, filters_from_namespace, refs_from_namespace, AdHocTreeToIndex
from dxr.plugins.xbl import refs, filters
from dxr.plugins.xbl.analyzer import XBLAnalyzer
from dxr.plugins.xbl.refs import PLUGIN_NAME


mappings = {
    LINE: {
        'properties': {
            # Method/prop/field definitions.
            PLUGIN_NAME + '_prop': QUALIFIED_LINE_NEEDLE,
            # Implementations of interfaces.
            PLUGIN_NAME + '_type': QUALIFIED_LINE_NEEDLE,
        }
    }
}


class FileToIndex(dxr.indexers.FileToIndex):
    def __init__(self, path, contents, plugin_name, tree):
        super(FileToIndex, self).__init__(path, contents, plugin_name, tree)
        self._analyzer = None

    @property
    def analyzer(self):
        if not self._analyzer:
            self._analyzer = XBLAnalyzer(self.path, self.tree,
                                         self.contents, self.tree.source_encoding)
        return self._analyzer

    def is_interesting(self):
        return (self.path.endswith('.xml') and '<bindings' in self.contents
                and super(FileToIndex, self).is_interesting())

    def refs(self):
        return self.analyzer.refs

    def needles_by_line(self):
        return iterable_per_line(
            with_start_and_end(split_into_lines(self.analyzer.needles)))


plugin = Plugin(
    tree_to_index=partial(AdHocTreeToIndex,
                          file_to_index_class=FileToIndex),
    refs=refs_from_namespace(refs.__dict__),
    filters=filters_from_namespace(filters.__dict__),
    mappings=mappings)
