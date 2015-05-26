import subprocess
import urlparse
import marshal
import os
from os.path import relpath, join
from ordereddict import OrderedDict

from funcy import memoize
# TODO next: use hglib rather than mercurial
from mercurial import hg, ui

"""Let DXR understand the concept of version control systems. The main entry
points are `tree_to_repos`, which produces a mapping of roots to VCS objects
for each version control root discovered under the provided tree, and
`path_to_vcs`, which returns a VCS object for the version control system that
tracks the given path. Currently supported VCS are Mercurial, Git, and
Perforce.
"""

class VCS(object):
    """A class representing an abstract notion of a version-control system.
    In general, all path arguments to query methods should be normalized to be
    relative to the root directory of the VCS.
    """

    def __init__(self, root, command):
        self.root = root
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

    def get_contents(self, path, revision):
        """Return contents of file at specified path at given revision."""
        return NotImplemented

    def display_rev(self, path):
        """Return a human-readable revision identifier for the repository."""
        return NotImplemented

class Mercurial(VCS):
    def __init__(self, root):
        super(Mercurial, self).__init__(root, 'hg')
        # We can't hold onto repo because it is not pickleable, so we only use
        # it during construction.
        repo = hg.repository(ui.ui(), root)
        tipctx = repo['tip']
        self.manifest = set(tipctx.manifest())
        # Find the revision, sometimes ends with a +.
        self.revision = str(tipctx).rstrip('+').strip()
        # Determine the revision on which each file has changed
        self.previous_revisions = self.find_previous_revisions(repo, root)

    def find_previous_revisions(self, repo, root):
        """Find the last revision in which each file changed, for diff links.

        Return a mapping {filename: [commits in which this file changed]}

        """
        last_change = {}
        for rev in xrange(0, repo['tip'].rev() + 1):
            ctx = repo[rev]
            # Go through all filenames changed in this commit:
            for filename in ctx.files():
                if filename not in last_change:
                    last_change[filename] = []
                # str(ctx) gives us the 12-char hash for URLs.
                last_change[filename].append(str(ctx))
        return last_change

    @classmethod
    def claim_vcs_source(cls, path, dirs):
        if '.hg' in dirs:
            dirs.remove('.hg')
            return cls(path)
        return None

    def display_rev(self, path):
        return self.revision

    def is_tracked(self, path):
        return path in self.manifest

    def get_contents(self, path, revision):
        return self.invoke_vcs(['cat', '-r', revision, path])

class Git(VCS):
    def __init__(self, root):
        super(Git, self).__init__(root, 'git')
        self.tracked_files = set(line for line in
                                 self.invoke_vcs(['ls-files']).splitlines())
        self.revision = self.invoke_vcs(['rev-parse', 'HEAD']).strip()

    @classmethod
    def claim_vcs_source(cls, path, dirs):
        if '.git' in dirs:
            dirs.remove('.git')
            return cls(path)
        return None

    def display_rev(self, path):
        return self.revision[:10]

    def is_tracked(self, path):
        return path in self.tracked_files

    def get_contents(self, path, revision):
        return self.invoke_vcs(['show', revision + ':' + path])

class Perforce(VCS):
    def __init__(self, root):
        super(Perforce, self).__init__(root, 'p4')
        have = self._p4run(['have'])
        self.have = dict((x['path'][len(root) + 1:], x) for x in have)

    @classmethod
    def claim_vcs_source(cls, path, dirs):
        if 'P4CONFIG' not in os.environ:
            return None
        if os.path.exists(os.path.join(path, os.environ['P4CONFIG'])):
            return cls(path)
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

    def display_rev(self, path):
        info = self.have[path]
        return '#' + info['haveRev']

every_vcs = [Mercurial, Git, Perforce]

@memoize
def tree_to_repos(tree):
    """Given a TreeConfig, return a mapping {root: VCS object} where root is a
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
            attempt = vcs.claim_vcs_source(cwd, dirs)
            if attempt is not None:
                sources[attempt.root] = attempt

    # It's possible that the root of the tree is not a VCS by itself, so walk up
    # the hierarchy until we find a parent folder that is a VCS. If we can't
    # find any, then no VCSs exist for the top level of this repository.
    directory = tree.source_folder
    while directory != '/' and directory not in sources:
        directory = os.path.dirname(directory)
        for vcs in every_vcs:
            attempt = vcs.claim_vcs_source(directory, os.listdir(directory))
            if attempt is not None:
                sources[directory] = attempt
    lookup_order = sorted(sources.keys(), key=len, reverse=True)
    # We want to make sure that we look up source repositories by deepest
    # directory first.
    ordered_sources = OrderedDict()
    for key in lookup_order:
        ordered_sources[key] = sources[key]
    return ordered_sources

@memoize
def vcs_for_path(tree, path):
        """Given a tree and a path in the tree, find a source repository we
        know about that claims to track that file.

        :arg tree: TreeConfig object representing a source code tree
        :arg string path: a path to a file (not a folder)
        """
        abs_path = join(tree.source_folder, path)
        for directory, vcs in tree_to_repos(tree).iteritems():
            # This seems to be the easiest way to find "is abs_path in the subtree
            # rooted at directory?"
            if relpath(abs_path, directory).startswith('..'):
                continue
            if vcs.is_tracked(relpath(abs_path, vcs.get_root_dir())):
                return vcs
        return None

