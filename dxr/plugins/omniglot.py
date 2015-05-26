import marshal
import os
from os.path import relpath
import subprocess
import urlparse

from schema import Optional
from funcy import memoize

import dxr.indexers
from dxr.vcs import tree_to_repos, vcs_for_path
from dxr.utils import DXR_BLUEPRINT
from dxr.plugins import Plugin
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

def dispatch_vcs(vcs, mercurial, git, p4):
    """Based on the name of vcs, call and return the reslut of at most one of
    mercurial, git, or p4."""
    vcs_name = vcs.get_vcs_name()
    if vcs_name == "Mercurial":
        return mercurial()
    elif vcs_name == "Git":
        return git()
    elif vcs_name == "Perforce":
        return p4()


class FileToIndex(dxr.indexers.FileToIndex):
    """Adder of blame and external links to items under version control"""

    def generate_log(self, rel_path):
        """Generate log url given path on vcs."""
        def log_mercurial():
            return upstream + 'filelog/' + self.vcs.revision + '/' + rel_path

        def log_git():
            return upstream + "/commits/" + self.vcs.revision + "/" + rel_path

        def log_p4():
            return upstream + info['depotFile'] + '?ac=22#' + info['haveRev']
        upstream = construct_upstream_url(self.vcs, self.plugin_config)
        return dispatch_vcs(self.vcs, log_mercurial, log_git, log_p4)

    def generate_blame(self, rel_path):
        def blame_mercurial():
            return upstream + 'annotate/' + self.vcs.revision + '/' + rel_path

        def blame_git():
            return upstream + "/blame/" + self.vcs.revision + "/" + rel_path

        def blame_p4():
            info = self.vcs.have[path]
            return upstream + info['depotFile'] + '?ac=193'

        upstream = construct_upstream_url(self.vcs, self.plugin_config)
        return dispatch_vcs(self.vcs, blame_mercurial, blame_git, blame_p4)

    def generate_diff(self, rel_path):
        def diff_mercurial():
            # We generate link to diff with the last revision in which the file changed.
            return upstream + 'diff/' + self.vcs.previous_revisions[rel_path][-1] + '/' + rel_path

        def diff_git():
            # I really want to make this anchor on the file in question, but github
            # doesn't seem to do that nicely
            return upstream + "/commit/" + self.vcs.revision

        def diff_p4():
            info = self.vcs.have[path]
            haveRev = info['haveRev']
            prevRev = str(int(haveRev) - 1)
            return (upstream + info['depotFile'] + '?ac=19&rev1=' + prevRev +
                    '&rev2=' + haveRev)

        upstream = construct_upstream_url(self.vcs, self.plugin_config)
        return dispatch_vcs(self.vcs, diff_mercurial, diff_git, diff_p4)

    def generate_raw(self, rel_path):
        def raw_mercurial():
            return upstream + 'raw-file/' + self.vcs.revision + '/' + rel_path

        def raw_git():
            return upstream + "/raw/" + self.vcs.revision + "/" + rel_path

        def raw_p4():
            info = self.vcs.have[path]
            return upstream + info['depotFile'] + '?ac=98&rev1=' + info['haveRev']

        upstream = construct_upstream_url(self.vcs, self.plugin_config)
        return dispatch_vcs(self.vcs, raw_mercurial, raw_git, raw_p4)


    def links(self):
        def items():
            # TODO next: bring these URL generated code into this plugin, and move permalink into core.py
            yield 'log', "Log", self.generate_log(vcs_relative_path)
            yield 'blame', "Blame", self.generate_blame(vcs_relative_path)
            yield 'diff',  "Diff", self.generate_diff(vcs_relative_path)
            yield 'raw', "Raw", self.generate_raw(vcs_relative_path)
            yield 'permalink', "Permalink", url_for(DXR_BLUEPRINT + '.permalink',
                                                    tree=self.tree.name,
                                                    revision=self.vcs.revision,
                                                    path=vcs_relative_path)

        self.vcs = vcs_for_path(self.tree, self.path)
        if self.vcs:
            vcs_relative_path = relpath(self.absolute_path(), self.vcs.get_root_dir())
            yield (5,
                   '%s (%s)' % (self.vcs.get_vcs_name(), self.vcs.display_rev(vcs_relative_path)),
                   items())
        else:
            yield 5, 'Untracked file', []


@memoize
def construct_upstream_url(vcs, plugin_config):
    """Attempt to construct an upstream url for the given VCS."""
    def upstream_mercurial():
        # Make and normalize the upstream URL
        upstream = urlparse.urlparse(vcs.invoke_vcs(['paths', 'default']).strip())
        recomb = list(upstream)
        if upstream.scheme == 'ssh':
            recomb[0] == 'http'
        recomb[1] = upstream.hostname # Eliminate any username stuff
        # check if port is defined and add that to the url
        if upstream.port:
            recomb[1] += ":{}".format(upstream.port)
        recomb[2] = '/' + recomb[2].lstrip('/') # strip all leading '/', add one back
        if not upstream.path.endswith('/'):
            recomb[2] += '/' # Make sure we have a '/' on the end
        recomb[3] = recomb[4] = recomb[5] = '' # Just those three
        return urlparse.urlunparse(recomb)

    def upstream_git():
        source_urls = self.invoke_vcs(['remote', '-v']).split('\n')
        for src_url in source_urls:
            name, url, _ = src_url.split()
            # TODO: Why do we assume origin is upstream?
            if name == 'origin':
                if repo.startswith("git@github.com:"):
                    return "https://github.com/" + repo[len("git@github.com:"):]
                elif repo.startswith(("git://github.com/", "https://github.com/")):
                    if repo.endswith(".git"):
                        repo = repo[:-len(".git")]
                    if repo.startswith("git:"):
                        repo = "https" + repo[len("git"):]
                    return repo
                raise RuntimeError("Your git remote is not supported yet. Please use a "
                                "GitHub remote for now, or disable the omniglot "
                                "plugin.")

    def upstream_p4():
        return plugin_config.p4web_url

    return dispatch_vcs(vcs, upstream_mercurial, upstream_git, upstream_p4)


plugin = Plugin(
        config_schema={Optional('p4web_url', default='http://p4web/'): str})
