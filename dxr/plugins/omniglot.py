import marshal
import os
from os.path import relpath
import subprocess
import urlparse

from schema import Optional

import dxr.indexers
from dxr.plugins import Plugin
from dxr.vcs import tree_to_repos
from dxr.utils import DXR_BLUEPRINT
from flask import url_for

"""Omniglot - Speaking all commonly-used version control systems.
At present, this plugin is still under development, so not all features are
fully implemented.

Omniglot first scans the project directory looking for the hallmarks of a VCS
(such as the .hg or .git directory). It also looks for these in parent
directories in case DXR is only parsing a fraction of the repository. Once this
information is found, it attempts to extract upstream information about the
repository. From this information, it builds the necessary information to
reproduce the links.

Currently supported VCSes and upstream views:
- git (github)
- mercurial (hgweb)

Todos:
- add gitweb support for git
- add cvs, svn, bzr support
- produce in-DXR blame information using VCSs
- check if the mercurial paths are specific to Mozilla's customization or not.

"""

class TreeToIndex(dxr.indexers.TreeToIndex):
    def pre_build(self):
        """Find all the relevant VCS dirs in the project, and put them in
        ``self.source_repositories``. Put the most-local-first order of its
        keys in ``self.lookup_order``.

        """
        self.source_repositories = tree_to_repos(self.tree)
        # Note: we want to make sure that we look up source repositories by deepest
        # directory first.
        self.lookup_order = self.source_repositories.keys()
        self.lookup_order.sort(key=len, reverse=True)

    def file_to_index(self, path, contents):
        return FileToIndex(path,
                           contents,
                           self.plugin_name,
                           self.tree,
                           self.lookup_order,
                           self.source_repositories)


class FileToIndex(dxr.indexers.FileToIndex):
    """Adder of blame and external links to items under version control"""

    def __init__(self, path, contents, plugin_name, tree, lookup_order, source_repositories):
        super(FileToIndex, self).__init__(path, contents, plugin_name, tree)
        self.lookup_order = lookup_order
        self.source_repositories = source_repositories

    def links(self):
        def items():
            yield 'log', "Log", vcs.generate_log(vcs_relative_path)
            yield 'blame', "Blame", vcs.generate_blame(vcs_relative_path)
            yield 'diff',  "Diff", vcs.generate_diff(vcs_relative_path)
            yield 'raw', "Raw", vcs.generate_raw(vcs_relative_path)
            yield 'permalink', "Permalink", url_for(DXR_BLUEPRINT + '.permalink',
                                                    tree=self.tree.name,
                                                    revision=vcs.get_rev(vcs_relative_path),
                                                    path=vcs_relative_path)

        abs_path = self.absolute_path()
        vcs = self._find_vcs_for_file(abs_path)
        if vcs:
            vcs_relative_path = relpath(abs_path, vcs.get_root_dir())
            yield (5,
                   '%s (%s)' % (vcs.get_vcs_name(), vcs.get_rev(vcs_relative_path)),
                   items())
        else:
            yield 5, 'Untracked file', []

    def _find_vcs_for_file(self, abs_path):
        """Given an absolute path, find a source repository we know about that
        claims to track that file.

        """
        for directory in self.lookup_order:
            # This seems to be the easiest way to find "is abs_path in the subtree
            # rooted at directory?"
            if relpath(abs_path, directory).startswith('..'):
                continue
            vcs = self.source_repositories[directory]
            if vcs.is_tracked(relpath(abs_path, vcs.get_root_dir())):
                return vcs
        return None


plugin = Plugin(
        tree_to_index=TreeToIndex,
        config_schema={Optional('p4web_url', default='http://p4web/'): str})
