import marshal
import os
from os.path import relpath
import subprocess
import urlparse

import dxr.indexers

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

    @classmethod
    def claim_vcs_source(cls, path, dirs, tree):
        if '.hg' in dirs:
            dirs.remove('.hg')
            return cls(path)
        return None

    def get_rev(self, path):
        return self.revision

    def generate_log(self, path):
        return self.upstream + 'filelog/' + self.revision + '/' + path

    def generate_blame(self, path):
        return self.upstream + 'annotate/' + self.revision + '/' + path

    def generate_diff(self, path):
        previous_rev = self.invoke_vcs(['hg', 'log', '-r', 'last(file("{}"))'.format(path), '--style=compact']).strip()
        # pull out the commit hash from the compact log entry
        # ex: 1   2e86c4e11a82   2004-9-12 10:36 -0500   ancient
        #          ^wanted^
        previous_rev = previous_rev.split()[1]
        return self.upstream + 'diff/' + previous_rev + '/' + path

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
    def claim_vcs_source(cls, path, dirs, tree):
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
        elif repo.startswith("git://github.com/"):
            self._is_github = True
            if repo.endswith(".git"):
                repo = repo[:-len(".git")]
            return "https" + repo[len("git"):]
        raise Exception("I don't know what's going on")


class Perforce(VCS):
    def __init__(self, root, upstream):
        super(Perforce, self).__init__(root)
        have = self._p4run(['have'])
        self.have = dict((x['path'][len(root) + 1:], x) for x in have)
        self.upstream = upstream

    @classmethod
    def claim_vcs_source(cls, path, dirs, tree):
        if 'P4CONFIG' not in os.environ:
            return None
        if os.path.exists(os.path.join(path, os.environ['P4CONFIG'])):
            return cls(path,
                       getattr(tree, 'plugin_omniglot_p4web', 'http://p4web/'))
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


class TreeToIndex(dxr.indexers.TreeToIndex):
    def pre_build(self):
        """Find all the relevant VCS dirs in the project, and put them in
        ``self.source_repositories``. Put the most-local-first order of its
        keys in ``self.lookup_order``.

        """
        self.source_repositories = {}
        # Find all of the VCSs in the source directory:
        for cwd, dirs, files in os.walk(self.tree.source_folder):
            for vcs in every_vcs:
                attempt = vcs.claim_vcs_source(cwd, dirs, self.tree)
                if attempt is not None:
                    self.source_repositories[attempt.root] = attempt

        # It's possible that the root of the tree is not a VCS by itself, so walk up
        # the hierarchy until we find a parent folder that is a VCS. If we can't
        # find any, then no VCSs exist for the top level of this repository.
        directory = self.tree.source_folder
        while directory != '/' and directory not in self.source_repositories:
            directory = os.path.dirname(directory)
            for vcs in every_vcs:
                attempt = vcs.claim_vcs_source(directory,
                                               os.listdir(directory),
                                               self.tree)
                if attempt is not None:
                    self.source_repositories[directory] = attempt
        # Note: we want to make sure that we look up source repositories by deepest
        # directory first.
        self.lookup_order = self.source_repositories.keys()
        self.lookup_order.sort(key=len, reverse=True)

    def file_to_index(self, path, contents):
        return FileToIndex(path,
                           contents,
                           self.tree,
                           self.lookup_order,
                           self.source_repositories)


class FileToIndex(dxr.indexers.FileToIndex):
    """Adder of blame and external links to items under version control"""

    def __init__(self, path, contents, tree, lookup_order, source_repositories):
        super(FileToIndex, self).__init__(path, contents, tree)
        self.lookup_order = lookup_order
        self.source_repositories = source_repositories

    def links(self):
        def items():
            yield 'log', "Log", vcs.generate_log(vcs_relative_path)
            yield 'blame', "Blame", vcs.generate_blame(vcs_relative_path)
            yield 'diff',  "Diff", vcs.generate_diff(vcs_relative_path)
            yield 'raw', "Raw", vcs.generate_raw(vcs_relative_path)

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
