"""DXR's concept of version control systems

The main entry points are `tree_to_repos`, which produces a mapping of roots
to VCS objects for each version control root discovered under the provided
tree, and `path_to_vcs`, which returns a VCS object for the version control
system that tracks the given path. Currently supported VCSs are Mercurial,
Git, and Perforce.

Currently supported upstream views:
- Git (GitHub, Bitbucket)
- Mercurial (Bitbucket, hgweb)
- Perforce (any configured upstream conforming to the p4web format)

TODO:
- Add gitweb support for git.
- Add cvs, svn, bzr support.
- Produce in-DXR blame information using VCSs.

"""
import marshal
import os
from os.path import relpath, join, split
from pkg_resources import resource_filename
import subprocess
import urlparse
from warnings import warn

import hglib
from ordereddict import OrderedDict

from dxr.utils import without_ending


class Vcs(object):
    """A class representing an abstract notion of a version-control system.
    In general, all path arguments to query methods should be normalized to be
    relative to the root directory of the VCS.
    """

    def __init__(self, root):
        self.root = root
        # We track at most one upstream per repository, which is the one used to
        # generate links.
        self.upstream = None

    def get_root_dir(self):
        """Return the directory that is at the root of the VCS."""
        return self.root

    def get_vcs_name(self):
        """Return a recognizable name for the VCS."""
        return type(self).__name__

    @classmethod
    def invoke_vcs(cls, args, cwd, **kwargs):
        """Return the result of invoking the VCS command on the repository from
        given working directory, with extra kwargs passed along to the Popen
        constructor.
        """
        return subprocess.check_output([cls.command] + args, cwd=cwd, **kwargs)

    def is_tracked(self, path):
        """Does the repository track this file?"""
        raise NotImplementedError

    def has_upstream(self):
        """Does the repository have an upstream that we can use to generate
        links?
        """
        return self.upstream is not None

    def generate_log(self, path):
        """Construct URL to upstream view of log of file at path."""
        if not self.upstream:
            return "javascript:void(0)"
        return self.upstream.generate_log(self, path)

    def generate_diff(self, path):
        """Construct URL to upstream view of diff of file at path."""
        if not self.upstream:
            return "javascript:void(0)"
        return self.upstream.generate_diff(self, path)

    def generate_blame(self, path):
        """Construct URL to upstream view of blame on file at path."""
        if not self.upstream:
            return "javascript:void(0)"
        return self.upstream.generate_blame(self, path)

    def generate_raw(self, path):
        """Construct URL to upstream view to raw file at path."""
        if not self.upstream:
            return "javascript:void(0)"
        return self.upstream.generate_raw(self, path)

    @classmethod
    def get_contents(cls, path, revision, stderr=None):
        """Return contents of file at specified path at given revision, where path
        is an absolute path."""
        raise NotImplementedError

    def display_rev(self, path):
        """Return a human-readable revision identifier for the repository."""
        raise NotImplementedError


class _VcsUpstream(object):
    """A class representing an upstream of a VCS repository."""
    def __init__(self, upstream):
        """You normally want to create a _VcsUpstream from a URL using
        ``upstream_for_url`` to ensure that this upstream accepts the URL and
        it's properly formatted.

        :arg string upstream: URL of the upstream

        """
        self.upstream = upstream

    @classmethod
    def upstream_for_url(cls, url):
        """Return an upstream representing url, or None if url is not
        representable.

        """
        raise NotImplementedError

    @classmethod
    def upstream_from_provider(cls, url, providers):
        """Return an upstream for url from the list of upstream providers, or
        None if url doesn't match any provider.

        """
        for provider in providers:
            upstream_from_provider = provider.upstream_for_url(url)
            if upstream_from_provider:
                return upstream_from_provider
        return None

    def generate_log(self, repo, path):
        """Construct a URL to view of log of file at path in the given repo."""
        raise NotImplementedError

    def generate_diff(self, repo, path):
        """Construct a URL to view of diff of file at path in the given repo."""
        raise NotImplementedError

    def generate_blame(self, repo, path):
        """Construct a URL to view of blame on file at path in the given repo."""
        raise NotImplementedError

    def generate_raw(self, repo, path):
        """Construct a URL to view of raw file at path in the given repo."""
        raise NotImplementedError


def _clean_parsed_url(parsed_url, use_https):
    """Given parsed_url as from urlparse.urlparse, return a string version
    standardized for upstream URLs.

    :arg use_https: If True or parsed_url uses https:// then return an
    https:// URL, otherwise return http://

    """
    # Build a list of URL parts for a call to urlunparse.
    url_parts = [''] * 6
    url_parts[0] = ('https' if use_https or parsed_url.scheme == 'https'
                    else 'http')
    url_parts[1] = parsed_url.hostname
    if parsed_url.port:
        # If repo clones and repo web interface come from different services
        # then this is probably wrong.
        url_parts[1] += ":{}".format(parsed_url.port)
    # Strip all leading '/', add one back:
    url_parts[2] = '/' + parsed_url[2].lstrip('/')
    url_parts[2] = without_ending('.git', url_parts[2])
    if not url_parts[2].endswith('/'):
        url_parts[2] += '/'  # Make sure we have a '/' on the end
    return urlparse.urlunparse(url_parts)


def _clean_git_url(url, host):
    """Given url for a git remote, return a standardized version of url if it
    matches host, or return None if it doesn't.

    We handle the following formats (the trailing '.git' should be there, but
    we don't enforce that):
    http[s]|ssh|git://[user[:password]@]host[:port]/*[.git]
    git@host:*[.git]

    """
    if url.startswith(('https://', 'ssh://', 'http://', 'git://')):
        # https:// and ssh:// can come with or without a username/password, as
        # in either https://user:pass@github.com/ or just https://github.com -
        # just handle them all the same:
        url = urlparse.urlparse(url)
        if url.hostname == host:
            return _clean_parsed_url(url, True)
    elif url.startswith('git@%s:' % host):
        url = 'https://%s/%s' % (host, url[len('git@%s:' % host):])
        return without_ending('.git', url) + '/'
    return None


def _clean_hg_url(url, host=None, use_https=False):
    """Given url for an hg remote, return a standardized version of url if it
    matches host or host is None, or return None if it doesn't.

    We handle the following formats:
    http[s]|ssh://[user[:password]@]host[:port]/*

    :arg use_https: If True or url uses https:// then return an https://
    URL, otherwise return http://
    """
    if url.startswith(('https://', 'ssh://', 'http://')):
        url = urlparse.urlparse(url)
        if url.hostname and (host is None or url.hostname == host):
            return _clean_parsed_url(url, use_https)
    return None


class _HgwebUpstream(_VcsUpstream):
    """A class representing a remote conforming to the hgweb interface.

    This is the mercurial fallback upstream if no other matches.

    """
    @classmethod
    def upstream_for_url(cls, url):
        url = _clean_hg_url(url)
        return cls(url) if url else None

    def generate_log(self, repo, path):
        return self.upstream + 'filelog/' + repo.revision + '/' + path

    def generate_diff(self, repo, path):
        # We generate link to diff with the last revision in which the file changed.
        return self.upstream + 'diff/' + repo.previous_revisions[path] + '/' + path

    def generate_blame(self, repo, path):
        return self.upstream + 'annotate/' + repo.revision + '/' + path

    def generate_raw(self, repo, path):
        # The 'raw-file' command doesn't appear in 'hg help hgweb' with the others,
        # but that's what 'hg serve' and https://selenic.com/hg/ use, so I guess
        # that makes it standard for hgweb.
        return self.upstream + 'raw-file/' + repo.revision + '/' + path


class _BitbucketUpstream(_VcsUpstream):
    """A (partial) class representing a remote on Bitbucket.  The view commands
    and link structures on Bitbucket are the same for both Git and Mercurial
    repositories, so we're able to provide most functionality here for both
    Git and Hg remotes.

    """
    def generate_log(self, repo, path):
        return self.upstream + "history-node/" + repo.revision + "/" + path

    def generate_diff(self, repo, path):
        # Bitbucket looks up an implicit diff1 in which the file at rev diff2
        # last changed, so just give our current revision as diff2.
        return self.upstream + "diff/" + path + "?diff2=" + repo.revision

    def generate_blame(self, repo, path):
        return self.upstream + "annotate/" + repo.revision + "/" + path

    def generate_raw(self, repo, path):
        return self.upstream + "raw/" + repo.revision + "/" + path


class _HgBitbucketUpstream(_BitbucketUpstream):
    "A class representing a Bitbucket Mercurial remote."""
    @classmethod
    def upstream_for_url(cls, url):
        url = _clean_hg_url(url, 'bitbucket.org', True)
        return cls(url) if url else None


class _GitBitbucketUpstream(_BitbucketUpstream):
    "A class representing a Bitbucket Git remote."""
    @classmethod
    def upstream_for_url(cls, url):
        url = _clean_git_url(url, 'bitbucket.org')
        return cls(url) if url else None


class _GithubUpstream(_VcsUpstream):
    """A class representing a Github remote."""
    @classmethod
    def upstream_for_url(cls, url):
        url = _clean_git_url(url, 'github.com')
        return cls(url) if url else None

    def generate_log(self, repo, path):
        return self.upstream + 'commits/' + repo.revision + '/' + path

    def generate_diff(self, repo, path):
        # I really want to make this anchor on the file in question, but github
        # doesn't seem to do that nicely
        return self.upstream + 'commit/' + repo.revision

    def generate_blame(self, repo, path):
        return self.upstream + 'blame/' + repo.revision + '/' + path

    def generate_raw(self, repo, path):
        return self.upstream + 'raw/' + repo.revision + '/' + path


class Mercurial(Vcs):
    command = 'hg'
    remote_providers = [_HgBitbucketUpstream, _HgwebUpstream]

    def __init__(self, root):
        super(Mercurial, self).__init__(root)
        hgext = resource_filename('dxr', 'hgext/previous_revisions.py')
        with hglib.open(root,
                        configs=['extensions.previous_revisions=%s' % hgext]) as client:
            tip = client.tip()
            self.revision = tip.node
            self.previous_revisions = self._find_previous_revisions(client)
        self.upstream = self._construct_upstream_url()

    def _construct_upstream_url(self):
        with open(os.devnull, 'w') as devnull:
            try:
                upstream = self.invoke_vcs(['paths', 'default'],
                                           self.root, stderr=devnull).strip()
            except subprocess.CalledProcessError:
                return None   # No default path, so no upstream.
        return _VcsUpstream.upstream_from_provider(upstream,
                                                   Mercurial.remote_providers)

    def _find_previous_revisions(self, client):
        """Find the last revision in which each file changed, for diff links.

        Return a mapping {path: last commit node in which file at path changed}

        """
        last_change = {}
        for line in client.rawcommand(['previous-revisions']).splitlines():
            node, path = line.split(':', 1)
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

    @classmethod
    def get_contents(cls, path, revision, stderr=None):
        head, tail = split(path)
        return cls.invoke_vcs(['cat', '-r', revision, tail], head, stderr=stderr)


class Git(Vcs):
    command = 'git'
    remote_providers = [_GithubUpstream, _GitBitbucketUpstream]

    def __init__(self, root):
        super(Git, self).__init__(root)
        self.tracked_files = set(line for line in
                                 self.invoke_vcs(['ls-files'],
                                                 self.root).splitlines())
        self.revision = self.invoke_vcs(['rev-parse', 'HEAD'], self.root).strip()
        self.upstream = self._construct_upstream_url()

    def _construct_upstream_url(self):
        source_urls = self.invoke_vcs(['remote', '-v'], self.root).split('\n')
        for src_url in source_urls:
            if not src_url:
                continue
            name, repo, _ = src_url.split()
            # TODO: Why do we assume origin is upstream?
            if name == 'origin':
                return _VcsUpstream.upstream_from_provider(repo,
                                                           Git.remote_providers)

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

    @classmethod
    def get_contents(cls, path, revision, stderr=None):
        head, tail = split(path)
        return cls.invoke_vcs(['show', revision + ':./' + tail], head, stderr=stderr)


class _PerforceUpstream(_VcsUpstream):
    """A class representing a remote providing a p4web-type interface."""
    @classmethod
    def upstream_for_url(cls, url):
        return None # perforce upstream urls are provided by config

    def generate_log(self, repo, path):
        info = repo.have[path]
        return self.upstream + info['depotFile'] + '?ac=22#' + info['haveRev']

    def generate_diff(self, repo, path):
        info = repo.have[path]
        haveRev = info['haveRev']
        prevRev = str(int(haveRev) - 1)
        return (self.upstream + info['depotFile'] + '?ac=19&rev1=' + prevRev +
                '&rev2=' + haveRev)

    def generate_blame(self, repo, path):
        info = repo.have[path]
        return self.upstream + info['depotFile'] + '?ac=193'

    def generate_raw(self, repo, path):
        info = repo.have[path]
        return self.upstream + info['depotFile'] + '?ac=98&rev1=' + info['haveRev']


class Perforce(Vcs):
    command = 'p4'

    def __init__(self, root, upstream):
        super(Perforce, self).__init__(root)
        have = self._p4run(['have'])
        self.have = dict((x['path'][len(root) + 1:], x) for x in have)
        self.upstream = _PerforceUpstream(upstream) if upstream else None

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

    def display_rev(self, path):
        info = self.have[path]
        return '#' + info['haveRev']


every_vcs = [Mercurial, Git, Perforce]


def tree_to_repos(tree):
    """Given a TreeConfig, return a mapping {root: Vcs object} where root is a
    directory under tree.source_folder. Traversal of the returned mapping
    follows the order of deepest directory first.

    We operate under a couple of sensible assumptions:
    *) Git repositories are associated only with .git, Hg only with .hg (though
       I'm not sure that can even be changed in Hg - it can be in Git); and
    *) no given directory can be the root of more than one repository.

    :arg tree: TreeConfig object representing a source code tree

    """
    sources = {}
    # Find all of the VCSs in the source directory:
    # We may see multiple VCSs if we use git submodules, for example.
    for cwd, dirs, files in os.walk(tree.source_folder):
        for vcs in every_vcs:
            attempt = vcs.claim_vcs_source(cwd, dirs, tree)
            if attempt is not None:
                sources[cwd] = attempt
                break

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
                break
    # We want to make sure that we look up source repositories by deepest
    # directory first.
    lookup_order = sorted(sources.keys(), key=len, reverse=True)
    ordered_sources = OrderedDict()
    for key in lookup_order:
        ordered_sources[key] = sources[key]
    return ordered_sources


def file_contents_at_rev(abspath, revision):
    """Attempt to return the contents of a file at a specific revision."""
    with open(os.devnull, 'w') as devnull:
        for cls in [Mercurial, Git]:
            try:
                return cls.get_contents(abspath, revision, stderr=devnull)
            except subprocess.CalledProcessError:
                continue
    return None


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
        """Given a relative path to a file in the tree, return a source
        repository we know about that claims to track that file, or None if the
        file isn't tracked.

        :arg string path: a path, relative to self.tree.source_folder, to a file
        in tree

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
