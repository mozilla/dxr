"""Let DXR understand the concept of version control systems. The main entry
points are `tree_to_repos`, which produces a mapping of roots to VCS objects
for each version control root discovered under the provided tree, and
`path_to_vcs`, which returns a VCS object for the version control system that
tracks the given path. Currently supported VCS are Mercurial, Git, and
Perforce.

Currently supported upstream views:
- git (github)
- mercurial (hgweb)

Todos:
- add gitweb support for git
- add cvs, svn, bzr support
- produce in-DXR blame information using VCSs
- check if the mercurial paths are specific to Mozilla's customization or not.
"""
import marshal
import os
from os.path import relpath, join, dirname
import subprocess
import urlparse
from warnings import warn


import hglib
from ordereddict import OrderedDict

import dxr

class Vcs(object):
    """A class representing an abstract notion of a version-control system.
    In general, all path arguments to query methods should be normalized to be
    relative to the root directory of the VCS.
    """

    def __init__(self, root, command):
        self.root = root
        # shell command for VCS: 'hg' in Mercurial, 'git' for Git, etc.
        self.command = command

    def get_root_dir(self):
        """Return the directory that is at the root of the VCS."""
        return self.root

    def get_vcs_name(self):
        """Return a recognizable name for the VCS."""
        return type(self).__name__

    def invoke_vcs(self, args):
        """Return the result of invoking the VCS command on the repository,
        with the current working directory set to the root directory.
        """
        return subprocess.check_output([self.command] + args, cwd=self.get_root_dir())

    def is_tracked(self, path):
        """Does the repository track this file?"""
        return NotImplemented

    def generate_log(self, path):
        """Construct URL to upstream view of log of file at path."""
        return NotImplemented

    def generate_diff(self, path):
        """Construct URL to upstream view of diff of file at path."""
        return NotImplemented

    def generate_blame(self, path):
        """Construct URL to upstream view of blame on file at path."""
        return NotImplemented

    def generate_raw(self, path):
        """Construct URL to upstream view to raw file at path."""
        return NotImplemented

    def get_contents(self, path, revision):
        """Return contents of file at specified path at given revision."""
        return NotImplemented

    def display_rev(self, path):
        """Return a human-readable revision identifier for the repository."""
        return NotImplemented

class Mercurial(Vcs):
    def __init__(self, root):
        super(Mercurial, self).__init__(root, 'hg')
        hgext = join(dirname(dxr.__file__), 'hgext', 'previous_revisions.py')
        with hglib.open(root,
                        configs = ['extensions.previous_revisions=%s' % hgext]) as client:
            tip = client.tip()
            self.revision = tip.node
            self.previous_revisions = self.find_previous_revisions(client)
        self.upstream = self._construct_upstream_url()

    def _construct_upstream_url(self):
        upstream = urlparse.urlparse(self.invoke_vcs(['paths', 'default']).strip())
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

    def find_previous_revisions(self, client):
        """Find the last revision in which each file changed, for diff links.

        Return a mapping {path: last commit nodes in which file at path changed}

        """
        last_change = {}
        for line in client.rawcommand(['previous-revisions']).splitlines():
            path, node = line.split(':')
            last_change[path] = node
        return last_change

    @classmethod
    def claim_vcs_source(cls, path, dirs, tree):
        if '.hg' in dirs:
            dirs.remove('.hg')
            return cls(path)
        return None

    def display_rev(self, path):
        return self.revision[:12]

    def is_tracked(self, path):
        return path in self.previous_revisions

    def generate_raw(self, path):
        return self.upstream + 'raw-file/' + self.revision + '/' + path

    def generate_diff(self, path):
        # We generate link to diff with the last revision in which the file changed.
        return self.upstream + 'diff/' + self.previous_revisions[path] + '/' + path

    def generate_blame(self, path):
        return self.upstream + 'annotate/' + self.revision + '/' + path

    def generate_log(self, path):
        return self.upstream + 'filelog/' + self.revision + '/' + path

    def get_contents(self, path, revision):
        return self.invoke_vcs(['cat', '-r', revision, path])

class Git(Vcs):
    def __init__(self, root):
        super(Git, self).__init__(root, 'git')
        self.tracked_files = set(line for line in
                                 self.invoke_vcs(['ls-files']).splitlines())
        self.revision = self.invoke_vcs(['rev-parse', 'HEAD']).strip()
        self.upstream = self._construct_upstream_url()

    def _construct_upstream_url(self):
        source_urls = self.invoke_vcs(['remote', '-v']).split('\n')
        for src_url in source_urls:
            name, repo, _ = src_url.split()
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
                warn("Your git remote is not supported yet. Please use a "
                     "GitHub remote if you would like version control "
                     "naviagtion links to show.")
                break

    @classmethod
    def claim_vcs_source(cls, path, dirs, tree):
        if '.git' in dirs:
            dirs.remove('.git')
            return cls(path)
        return None

    def display_rev(self, path):
        return self.revision[:10]

    def is_tracked(self, path):
        return path in self.tracked_files

    def generate_raw(self, path):
        return self.upstream + "/raw/" + self.revision + "/" + path

    def generate_diff(self, path):
        # I really want to make this anchor on the file in question, but github
        # doesn't seem to do that nicely
        return self.upstream + "/commit/" + self.revision

    def generate_blame(self, path):
        return self.upstream + "/blame/" + self.revision + "/" + path

    def generate_log(self, path):
        return self.upstream + "/commits/" + self.revision + "/" + path

    def get_contents(self, path, revision):
        return self.invoke_vcs(['show', revision + ':' + path])

class Perforce(Vcs):
    def __init__(self, root, upstream):
        super(Perforce, self).__init__(root, 'p4')
        have = self._p4run(['have'])
        self.have = dict((x['path'][len(root) + 1:], x) for x in have)
        self.upstream = upstream

    @classmethod
    def claim_vcs_source(cls, path, dirs, tree):
        if 'P4CONFIG' not in os.environ:
            return None
        if os.path.exists(os.path.join(path, os.environ['P4CONFIG'])):
            return cls(path, tree.p4web_url)
        return None

    def _p4run(self, args):
        ret = []
        env = os.environ
        env["PWD"] = self.root
        proc = subprocess.Popen(['p4', '-G'] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            cwd=self.root,
            env=env)
        while True:
            try:
                x = marshal.load(proc.stdout)
            except EOFError:
                break
            ret.append(x)
        return ret

    def is_tracked(self, path):
        return path in self.have

    def generate_raw(self, path):
        info = self.have[path]
        return self.upstream + info['depotFile'] + '?ac=98&rev1=' + info['haveRev']

    def generate_diff(self, path):
        info = self.have[path]
        haveRev = info['haveRev']
        prevRev = str(int(haveRev) - 1)
        return (self.upstream + info['depotFile'] + '?ac=19&rev1=' + prevRev +
                '&rev2=' + haveRev)

    def generate_blame(self, path):
        info = self.have[path]
        return self.upstream + info['depotFile'] + '?ac=193'

    def generate_log(self, path):
        info = self.have[path]
        return self.upstream + info['depotFile'] + '?ac=22#' + info['haveRev']

    def display_rev(self, path):
        info = self.have[path]
        return '#' + info['haveRev']

every_vcs = [Mercurial, Git, Perforce]

def tree_to_repos(tree):
    """Given a TreeConfig, return a mapping {root: Vcs object} where root is a
    directory under tree.source_folder where root is a directory under
    tree.source_folder. Traversal of the returned mapping follows the order of
    deepest directory first.

    :arg tree: TreeConfig object representing a source code tree

    """
    sources = {}
    # Find all of the VCSs in the source directory:
    # We may see multiple VCS if we use git submodules, for example.
    for cwd, dirs, files in os.walk(tree.source_folder):
        for vcs in every_vcs:
            attempt = vcs.claim_vcs_source(cwd, dirs, tree)
            if attempt is not None:
                sources[attempt.root] = attempt

    # It's possible that the root of the tree is not a VCS by itself, so walk up
    # the hierarchy until we find a parent folder that is a VCS. If we can't
    # find any, then no VCSs exist for the top level of this repository.
    directory = tree.source_folder
    while directory != '/' and directory not in sources:
        directory = os.path.dirname(directory)
        for vcs in every_vcs:
            attempt = vcs.claim_vcs_source(directory, os.listdir(directory), tree)
            if attempt is not None:
                sources[directory] = attempt
    lookup_order = sorted(sources.keys(), key=len, reverse=True)
    # We want to make sure that we look up source repositories by deepest
    # directory first.
    ordered_sources = OrderedDict()
    for key in lookup_order:
        ordered_sources[key] = sources[key]
    return ordered_sources


class VcsCache(object):
    """This class offers a way to obtain Vcs objects for any file within a
    given tree."""
    def __init__(self, tree):
        """Construct a VcsCache for the given tree.

        :arg tree: TreeConfig object representing a source code tree

        """
        self.tree = tree
        self.repos = tree_to_repos(tree)
        self._path_cache = {}

    def vcs_for_path(self, path):
        """Given a tree and a path in the tree, find a source repository we
        know about that claims to track that file.

        :arg string path: a path to a file (not a folder)
        """
        if path in self._path_cache:
            return self._path_cache[path]
        abs_path = join(self.tree.source_folder, path)
        for directory, vcs in self.repos.iteritems():
            # This seems to be the easiest way to find "is abs_path in the subtree
            # rooted at directory?"
            if relpath(abs_path, directory).startswith('..'):
                continue
            if vcs.is_tracked(relpath(abs_path, vcs.get_root_dir())):
                self._path_cache[path] = vcs
                break
        return self._path_cache.get(path)

