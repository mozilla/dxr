"""Extmatch - Match files in a given folder by extension and provide a link
in the nav panel of each to the other.

Currently we match "Header" file extensions with "Implementation" file
extensions.
"""

from fnmatch import fnmatchcase
import os
from os.path import join, basename, splitext, isfile
from collections import namedtuple

from dxr.indexers import (FileToIndex as FileToIndexBase,
                          TreeToIndex as TreeToIndexBase)
from dxr.mime import icon
from dxr.utils import browse_file_url, unicode_for_display


# A list of extensions along with a title describing the type of extensions:
_TitledExts = namedtuple('_TitledExts', ['exts', 'title'])


class TreeToIndex(TreeToIndexBase):
    def __init__(self, plugin_name, tree, vcs_cache):
        super(TreeToIndex, self).__init__(plugin_name, tree, vcs_cache)
        self.header_exts = _TitledExts(['.h', '.hxx', '.hpp'], 'Header')
        self.impl_exts = _TitledExts(['.cpp', '.c', '.cc', '.cxx', '.mm'],
                                     'Implementation')

    def file_to_index(self, path, contents):
        return FileToIndex(path,
                           contents,
                           self.plugin_name,
                           self.tree,
                           (self.header_exts, self.impl_exts))


class FileToIndex(FileToIndexBase):
    def __init__(self, path, contents, plugin_name, tree, ext_pairings):
        super(FileToIndex, self).__init__(path, contents, plugin_name, tree)
        self.ext_pairings = ext_pairings

    def links(self):
        """Add a link from this file to another in the same folder with a
        matching extension, when such a file exists.
        """
        def dual_exts_for(ext):
            if ext in self.ext_pairings[0].exts:
                return self.ext_pairings[1]
            if ext in self.ext_pairings[1].exts:
                return self.ext_pairings[0]
            return _TitledExts((), '')

        def is_indexed(path):
            if any(fnmatchcase(basename(path), e)
                   for e in self.tree.ignore_filenames):
                return False
            if any(fnmatchcase('/' + path.replace(os.sep, '/'), e)
                   for e in self.tree.ignore_paths):
                return False
            return True

        path_no_ext, ext = splitext(self.path)
        dual_exts = dual_exts_for(ext)
        for dual_ext in dual_exts.exts:
            dual_path = path_no_ext + dual_ext
            if (isfile(join(self.tree.source_folder, dual_path)) and
                is_indexed(dual_path)):
                yield (4,
                       dual_exts.title,
                       [(icon(dual_path),
                        unicode_for_display(basename(dual_path)),
                        browse_file_url(self.tree.name,
                                        unicode_for_display(dual_path)))])
                # Todo? this 'break' breaks handling of multiple extension
                # pairings on the same basename.
                break
