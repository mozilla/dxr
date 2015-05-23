import marshal
import os
from os.path import relpath
import subprocess
import urlparse

from schema import Optional

import dxr.indexers
from dxr.vcs import tree_to_repos, vcs_for_path
from dxr.utils import DXR_BLUEPRINT
from flask import url_for

"""Omniglot - Speaking all commonly-used web views of version control systems.
At present, this plugin is still under development, so not all features are
fully implemented.

Currently supported upstream views:
- git (github)
- mercurial (hgweb)

Todos:
- add gitweb support for git
- add cvs, svn, bzr support
- produce in-DXR blame information using VCSs
- check if the mercurial paths are specific to Mozilla's customization or not.
"""

class FileToIndex(dxr.indexers.FileToIndex):
    """Adder of blame and external links to items under version control"""

    def links(self):
        def items():
            yield 'log', "Log", vcs.generate_log(vcs_relative_path)
            yield 'blame', "Blame", vcs.generate_blame(vcs_relative_path)
            yield 'diff',  "Diff", vcs.generate_diff(vcs_relative_path)
            yield 'raw', "Raw", vcs.generate_raw(vcs_relative_path)
            yield 'permalink', "Permalink", url_for(DXR_BLUEPRINT + '.permalink',
                                                    tree=self.tree.name,
                                                    revision=vcs.revision,
                                                    path=vcs_relative_path)

        vcs = vcs_for_path(self.tree, self.path)
        if vcs:
            vcs_relative_path = relpath(self.absolute_path(), vcs.get_root_dir())
            yield (5,
                   '%s (%s)' % (vcs.get_vcs_name(), vcs.display_rev(vcs_relative_path)),
                   items())
        else:
            yield 5, 'Untracked file', []

