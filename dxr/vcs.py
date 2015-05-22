import subprocess
import urlparse
import marshal
import os
from os.path import relpath

"""Let DXR understand the concept of version control systems."""

class VCS(object):
    """A class representing an abstract notion of a version-control system.
    In general, all path arguments to query methods should be normalized to be
    relative to the root directory of the VCS.
    """

    def __init__(self, root):
        self.root = root
        self.untracked_files = set()

    def get_root_dir(self):
        """Return the directory that is at the root of the VCS."""
        return self.root

    def get_vcs_name(self):
        """Return a recognizable name for the VCS."""
        return type(self).__name__

    def invoke_vcs(self, args):
        """Return the result of invoking said command on the repository, with
        the current working directory set to the root directory.
        """
        return subprocess.check_output(args, cwd=self.get_root_dir())

    def is_tracked(self, path):
        """Does the repository track this file?"""
        return path not in self.untracked_files

    def get_contents(self, path, revision):
        """Return contents of file at specified path at given revision."""
        return None

    def get_rev(self, path):
        """Return a human-readable revision identifier for the repository."""
        return NotImplemented

    def generate_log(self, path):
        """Return a URL for a page that lists revisions for this file."""
        return NotImplemented

    def generate_blame(self, path):
        """Return a URL for a page that lists source annotations for lines in
        this file.
        """
        return NotImplemented

    def generate_diff(self, path):
        """Return a URL for a page that shows the last change made to this file.
        """
        return NotImplemented

    def generate_raw(self, path):
        """Return a URL for a page that returns a raw copy of this file."""
        return NotImplemented

class Mercurial(VCS):
    def __init__(self, root):
        super(Mercurial, self).__init__(root)
        # Find the revision
        self.revision = self.invoke_vcs(['hg', 'id', '-i']).strip()
        # Sometimes hg id returns + at the end.
        if self.revision.endswith("+"):
            self.revision = self.revision[:-1]

        # Make and normalize the upstream URL
        upstream = urlparse.urlparse(self.invoke_vcs(['hg', 'paths', 'default']).strip())
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
        self.upstream = urlparse.urlunparse(recomb)

        # Find all untracked files
        self.untracked_files = set(line.split()[1] for line in
            self.invoke_vcs(['hg', 'status', '-u', '-i']).split('\n')[:-1])

        # Determine the revision on which each file has changed
        self.previous_revisions = self.find_previous_revisions(root)

    def find_previous_revisions(self, root):
        """Find the last revision in which each file changed, for diff links.

        Return a mapping {filename: [commits in which this file changed]}

        """
        from mercurial import hg, ui  # Note: Mercurial doesn't support this api.
        repo = hg.repository(ui.ui(), root)
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
    def claim_vcs_source(cls, path, dirs, tree_config):
        if '.hg' in dirs:
            dirs.remove('.hg')
            return cls(path)
        return None

    def get_rev(self, path):
        return self.revision

    def get_contents(self, path, revision):
        return self.invoke_vcs(['hg', 'cat', '-r', revision, path])

    def generate_log(self, path):
        return self.upstream + 'filelog/' + self.revision + '/' + path

    def generate_blame(self, path):
        return self.upstream + 'annotate/' + self.revision + '/' + path

    def generate_diff(self, path):
        # We generate link to diff with the last revision in which the file changed.
        return self.upstream + 'diff/' + self.previous_revisions[path][-1] + '/' + path

    def generate_raw(self, path):
        return self.upstream + 'raw-file/' + self.revision + '/' + path

class Git(VCS):
    def __init__(self, root):
        super(Git, self).__init__(root)
        self.untracked_files = set(line for line in
            self.invoke_vcs(['git', 'ls-files', '-o']).split('\n')[:-1])
        self.revision = self.invoke_vcs(['git', 'rev-parse', 'HEAD'])
        source_urls = self.invoke_vcs(['git', 'remote', '-v']).split('\n')
        for src_url in source_urls:
            name, url, _ = src_url.split()
            if name == 'origin':
                self.upstream = self.synth_web_url(url)
                break

    @classmethod
    def claim_vcs_source(cls, path, dirs, tree_config):
        if '.git' in dirs:
            dirs.remove('.git')
            return cls(path)
        return None

    def get_rev(self, path):
        return self.revision[:10]

    def generate_log(self, path):
        return self.upstream + "/commits/" + self.revision + "/" + path

    def generate_blame(self, path):
        return self.upstream + "/blame/" + self.revision + "/" + path

    def generate_diff(self, path):
        # I really want to make this anchor on the file in question, but github
        # doesn't seem to do that nicely
        return self.upstream + "/commit/" + self.revision

    def generate_raw(self, path):
        return self.upstream + "/raw/" + self.revision + "/" + path

    def synth_web_url(self, repo):
        if repo.startswith("git@github.com:"):
            self._is_github = True
            return "https://github.com/" + repo[len("git@github.com:"):]
        elif repo.startswith(("git://github.com/", "https://github.com/")):
            self._is_github = True
            if repo.endswith(".git"):
                repo = repo[:-len(".git")]
            if repo.startswith("git:"):
                repo = "https" + repo[len("git"):]
            return repo
        raise RuntimeError("Your git remote is not supported yet. Please use a "
                           "GitHub remote for now, or disable the omniglot "
                           "plugin.")

class Perforce(VCS):
    def __init__(self, root, upstream):
        super(Perforce, self).__init__(root)
        have = self._p4run(['have'])
        self.have = dict((x['path'][len(root) + 1:], x) for x in have)
        self.upstream = upstream

    @classmethod
    def claim_vcs_source(cls, path, dirs, tree_config):
        if 'P4CONFIG' not in os.environ:
            return None
        if os.path.exists(os.path.join(path, os.environ['P4CONFIG'])):
            return cls(path, tree_config.p4web_url)
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

    def get_rev(self, path):
        info = self.have[path]
        return '#' + info['haveRev']

    def generate_log(self, path):
        info = self.have[path]
        return self.upstream + info['depotFile'] + '?ac=22#' + info['haveRev']

    def generate_blame(self, path):
        info = self.have[path]
        return self.upstream + info['depotFile'] + '?ac=193'

    def generate_diff(self, path):
        info = self.have[path]
        haveRev = info['haveRev']
        prevRev = str(int(haveRev) - 1)
        return (self.upstream + info['depotFile'] + '?ac=19&rev1=' + prevRev +
                '&rev2=' + haveRev)

    def generate_raw(self, path):
        info = self.have[path]
        return self.upstream + info['depotFile'] + '?ac=98&rev1=' + info['haveRev']

every_vcs = [Mercurial, Git, Perforce]

def tree_to_repos(tree):
    """
    Given a TreeConfig, return a mapping {root: VCS object} where root is a
    directory under tree.source_folder where root is a directory under
    tree.source_folder.
    """
    sources = {}
    # Find all of the VCSs in the source directory:
    # We may see this if we use git submodules, for example.
    for cwd, dirs, files in os.walk(tree.source_folder):
        for vcs in every_vcs:
            attempt = vcs.claim_vcs_source(cwd, dirs, tree.config)
            if attempt is not None:
                sources[attempt.root] = attempt

    # It's possible that the root of the tree is not a VCS by itself, so walk up
    # the hierarchy until we find a parent folder that is a VCS. If we can't
    # find any, then no VCSs exist for the top level of this repository.
    directory = tree.source_folder
    while directory != '/' and directory not in sources:
        directory = os.path.dirname(directory)
        for vcs in every_vcs:
            attempt = vcs.claim_vcs_source(directory,
                                            os.listdir(directory),
                                            tree.config)
            if attempt is not None:
                sources[directory] = attempt
    return sources

