from collections import namedtuple
import json
import subprocess
from os.path import basename, dirname, relpath, join, exists

from dxr.plugins.js.refs import PLUGIN_NAME, QualifiedRef
import dxr.indexers
from dxr.indexers import (Extent, Position, iterable_per_line_sorted,
                          with_start_and_end)


# loc is (row, (col_start, col_end)).
AnalysisSchema = namedtuple('AnalysisSchema', ['loc', 'kind', 'type', 'name', 'sym'])


def to_analysis(line):
    """Convert a json-parsed line into an AnalysisSchema.
    """
    row, col = line['loc'].split(':', 1)
    if '-' in col:
        col = tuple(map(int, col.split('-', 1)))
    else:
        col = int(col), int(col)
    line['loc'] = int(row), col
    return AnalysisSchema(**line)


class TreeToIndex(dxr.indexers.TreeToIndex):
    """Start up the node scripts to analyze the tree.
    """
    def __init__(self, plugin_name, tree, vcs_cache):
        super(TreeToIndex, self).__init__(plugin_name, tree, vcs_cache)
        self.plugin_folder = dirname(__file__)

    def post_build(self):
        # Execute the esprima to dump metadata, by running node from here and
        # passing in the tree location
        retcode = subprocess.call(['node', 'analyze_tree.js',
                                   self.tree.source_folder,
                                   join(self.tree.temp_folder, 'plugins/js')] +
                                   self.tree.ignore_filenames,
                                  cwd=join(self.plugin_folder, 'analyze_js'))
        return retcode

    def file_to_index(self, path, contents):
        return FileToIndex(path, contents, self.plugin_name, self.tree)


class FileToIndex(dxr.indexers.FileToIndex):
    def __init__(self, path, contents, plugin_name, tree):
        super(FileToIndex, self).__init__(path, contents, plugin_name, tree)
        self.analysis_path = join(join(join(tree.temp_folder, 'plugins/js'),
                                       relpath(dirname(self.absolute_path()), tree.source_folder)),
                                  basename(path) + '.data')
        # All lines from the analysis output file.
        self.lines = []
        # Map of line number -> byte offset to use for emitting refs.
        self.offsets = []
        if self.is_interesting():
            with open(self.analysis_path) as analysis:
                self.lines = sorted((self.parse_analysis(line) for line in analysis), key=lambda x: x.loc)

    def is_interesting(self):
        return super(FileToIndex, self).is_interesting() and exists(self.analysis_path)

    def parse_analysis(self, line):
        """Convert JSON line string into a AnalysisSchema object.
        """
        return json.loads(line, object_hook=to_analysis)

    def build_ref(self, row, start, end, ref):
        """Create a 3-tuple from given line, start and end columns, and ref.
        """
        return self.char_offset(row, start), self.char_offset(row, end), ref

    def build_needle(self, filter_name, line, start, end, name, qualname=None):
        """Create a needle mapping for the given filter, line, start and end
        columns, and name.
        """
        # If qualname is not provided, then use name.
        mapping = {'name': name, 'qualname': qualname or name}
        return (PLUGIN_NAME + '_' + filter_name, mapping,
                Extent(Position(row=line, col=start), Position(row=line, col=end)))

    def needles_by_line(self):
        def all_needles():
            for line in self.lines:
                row, (start, end) = line.loc
                typ = line.type
                if line.kind == 'use':
                    typ += '_ref'
                yield self.build_needle(typ, row, start, end, line.name, line.sym)

        return iterable_per_line_sorted(with_start_and_end(all_needles()))

    def refs(self):
        for line in self.lines:
            row, (start, end) = line.loc
            qref = QualifiedRef(self.tree, (line.sym, line.name, line.type), qualname=line.sym)
            yield self.build_ref(row, start, end, qref)
