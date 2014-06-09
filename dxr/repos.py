import git
import hglib
import marshal
import os
import subprocess
import urlparse

# Global variables
tree = None
source_repositories = {}

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

    def get_repo_name(self):
        """Return the directory name of the VCS."""
        raise NotImplemented

    def invoke_vcs(self, args):
        """Return the result of invoking said command on the repository, with
        the current working directory set to the root directory.
        """
        return subprocess.check_output(args, cwd=self.get_root_dir())

    def is_tracked(self, path):
        """Does the repository track this file?"""
        return path not in self.untracked_files

    def get_rev(self, path):
        """Return a human-readable revision identifier for the repository."""
        raise NotImplemented

    def generate_log(self, path):
        """Return a URL for a page that lists revisions for this file."""
        raise NotImplemented

    def generate_blame(self, path):
        """Return a URL for a page that lists source annotations for lines in
        this file.
        """
        raise NotImplemented

    def generate_diff(self, path):
        """Return a URL for a page that shows the last change made to this file.
        """
        raise NotImplemented

    def generate_raw(self, path):
        """Return a URL for a page that returns a raw copy of this file."""
        raise NotImplemented


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
        recomb[2] = '/' + recomb[2].lstrip('/') # strip all leading '/', add one back
        if not upstream.path.endswith('/'):
            recomb[2] += '/' # Make sure we have a '/' on the end
        recomb[3] = recomb[4] = recomb[5] = '' # Just those three
        # want this for permalink names and url root
        self.upstream_name = recomb[2]
        self.upstream = urlparse.urlunparse(recomb)

        # Find all untracked files
        self.untracked_files = set(line.split()[1] for line in
            self.invoke_vcs(['hg', 'status', '-u', '-i']).split('\n')[:-1])

    @staticmethod
    def claim_vcs_source(path, dirs):
        if '.hg' in dirs:
            dirs.remove('.hg')
            return Mercurial(path)
        return None

    def get_file_revision(self, args):
        # parse the incoming args into revision and file names
        revision = args[0]
        file = args[1]
        # open hg repo
        repo = hglib.open(self.root)
        # extract file contents at given revision
        # hglib.cat requires a list as an argument even for a single file
        code = repo.cat([self.root + '/' + file], revision)
        return code 

    def get_rev(self, path):
        return self.revision

    def generate_log(self, path):
        return self.upstream + 'filelog/' + self.revision + '/' + path

    def generate_blame(self, path):
        return self.upstream + 'annotate/' + self.revision + '/' + path

    def generate_diff(self, path):
        return self.upstream + 'diff/' + self.revision + '/' + path

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
            self.upstream = self.synth_web_url(url)
            break

    @staticmethod
    def claim_vcs_source(path, dirs):
        if '.git' in dirs:
            dirs.remove('.git')
            return Git(path)
        return None

    def get_file_revision(self, args):
        # parse the incoming args into revision and file names
        revision = args[0]
        file = args[1]
        # open the underlying git repo
        repo = git.Repo(self.root)
        # call git show on the file
        code = repo.git.execute(['git','show', '%s:%s' % (revision, file) ])
        return code

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
        elif repo.startswith("git://github.com/"):
            self._is_github = True
            if repo.endswith(".git"):
                repo = repo[:-len(".git")]
            return "https" + repo[len("git"):]
        else:
            return repo
        raise Exception("I don't know what's going on")


class Perforce(VCS):
    def __init__(self, root):
        super(Perforce, self).__init__(root)
        have = self._p4run(['have'])
        self.have = dict((x['path'][len(root) + 1:], x) for x in have)
        try:
            self.upstream = tree.plugin_omniglot_p4web
        except AttributeError:
            self.upstream = "http://p4web/"

    @staticmethod
    def claim_vcs_source(path, dirs):
        if 'P4CONFIG' not in os.environ:
            return None
        if os.path.exists(os.path.join(path, os.environ['P4CONFIG'])):
            return Perforce(path)
        return None

    def get_file_revision(self, args):
        raise NotImplemented

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


# Load global variables
def load(tree_, conn=None):
    # conn looks to be unused?
    global tree, lookup_order
    tree = tree_
    # Find all of the VCS's in the source directory
    for cwd, dirs, files in os.walk(tree.get_root_dir()):
        for vcs in every_vcs:
            attempt = vcs.claim_vcs_source(cwd, dirs)
            if attempt is not None:
                source_repositories[attempt.root] = attempt
    # for functions that need it, return the source_repositories, e.g. permalink route in flask
    return source_repositories


def find_vcs_for_file(path):
    """Given an absolute path, find a source repository we know about that
    claims to track that file.
    """
    for directory in lookup_order:
        # This seems to be the easiest way to find "is path in the subtree
        # rooted at directory?"
        if os.path.relpath(path, directory).startswith('..'):
            continue
        vcs = source_repositories[directory]
        if vcs.is_tracked(os.path.relpath(path, vcs.get_root_dir())):
            return vcs
    return None