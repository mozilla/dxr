"""Omniglot - Speaking all commonly-used web views of version control systems.
At present, this plugin is still under development, so not all features are
fully implemented.
"""

from os.path import relpath

import dxr.indexers

class TreeToIndex(dxr.indexers.TreeToIndex):
    def file_to_index(self, path, contents):
        return FileToIndex(path,
                           contents,
                           self.plugin_name,
                           self.tree,
                           self.vcs_cache.vcs_for_path(path))

class FileToIndex(dxr.indexers.FileToIndex):
    """Adder of blame and external links to items under version control"""

    def __init__(self, path, contents, plugin_name, tree, vcs):
        super(FileToIndex, self).__init__(path, contents, plugin_name, tree)
        self.vcs = vcs

    def is_interesting(self):
        return not self.is_link()

    def links(self):
        def items():
            log = self.vcs.generate_log(vcs_relative_path)
            if log:
                yield 'log', "Log", log

            blame = self.vcs.generate_blame(vcs_relative_path)
            if blame:
                yield 'blame', "Blame", blame

            diff = self.vcs.generate_diff(vcs_relative_path)
            if diff:
                yield 'diff',  "Diff", diff

            raw = self.vcs.generate_raw(vcs_relative_path)
            if raw:
                yield 'raw', "Raw", raw

        if self.vcs and self.vcs.has_upstream():
            vcs_relative_path = relpath(self.absolute_path(), self.vcs.get_root_dir())
            yield (5, 'VCS Links', items())
