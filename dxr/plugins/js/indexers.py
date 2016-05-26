from itertools import imap
import json
import subprocess
from os.path import basename, dirname, relpath, join, exists

from dxr.plugins.js.refs import PLUGIN_NAME, QualifiedRef
import dxr.indexers
from dxr.indexers import (Extent, Position, iterable_per_line,
                          with_start_and_end, split_into_lines)
from dxr.utils import cumulative_sum


class ReadAnalysis(object):
    def __init__(self, tree, lines, contents):
        self.needles = []
        self.refs = []
        # Build map of line number -> byte offset to use for emitting refs.
        self.offsets = list(cumulative_sum(imap(len, contents.splitlines(True))))
        for line in lines:
            row, (start, end) = line['loc']
            qref = QualifiedRef(tree, (line['sym'], line['name'], line['type']), qualname=line['sym'])
            typ = line['type']
            if line['kind'] == 'use':
                typ += '_ref'
            self.yield_needle(typ, row, start, end, line['name'], line['sym'])
            self.yield_ref(row, start, end, qref)

    def yield_ref(self, row, start, end, ref):
        offset = self.row_to_offset(row)
        self.refs.append((offset + start, offset + end, ref))

    def row_to_offset(self, line):
        """Return the byte offset in the file of given line number.
        """
        return self.offsets[line - 1]

    def yield_needle(self, filter_name, line, start, end, name, qualname=None):
        """Add needle for qualified filter_name from line:start
        to line:end with given name and qualname.
        """
        # If qualname is not provided, then use name.
        mapping = {'name': name, 'qualname': qualname or name}
        self.needles.append((PLUGIN_NAME + '_' + filter_name,
                             mapping,
                             Extent(Position(row=line, col=start), Position(row=line, col=end))))


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
        lines = []
        if self.is_interesting():
            with open(self.analysis_path) as analysis:
                lines = self.parse_analysis(analysis.readlines())
            lines = sorted(lines, key=lambda x: x['loc'])
        self.analyzer = ReadAnalysis(tree, lines, contents)

    def is_interesting(self):
        return exists(self.analysis_path)

    def parse_analysis(self, lines):
        def parse_loc(line):
            if 'loc' in line:
                row, col = line['loc'].split(':', 1)
                if '-' in col:
                    col = tuple(map(int, col.split('-', 1)))
                else:
                    col = int(col), int(col)
                line['loc'] = int(row), col
            return line

        return (parse_loc(json.loads(line)) for line in lines)

    def needles_by_line(self):
        return iterable_per_line(with_start_and_end(split_into_lines(self.analyzer.needles)))

    def refs(self):
        return self.analyzer.refs
