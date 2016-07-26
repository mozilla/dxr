"""Continuous deployment script for DXR

Glossary
========

build directory - A folder, typically in the ``builds`` folder, containing
these folders...

    dxr - A checkout of the DXR source code
    virtualenv - A virtualenv with DXR and its dependencies installed

    Builds are named after an excerpt of their git hashes and are symlinked
    into the base directory.

base directory - The folder containing these folders...

    builds - A folder of builds, including the current production and staging
        ones
    dxr-<kind> - A symlink to the current build of a given kind

"""
# When we need to make this work across multiple nodes:
# I really have no reason to use Commander over Fabric: I don't need Chief, and
# nearly all the features and conveniences Commander had over Fabric have been
# since implemented in Fabric. Fabric has more features and more support and
# was released more recently. OTOH, Fabric's argument conventions are crazy.

# TODO: Update the deployment script first, and use the new version to deploy.
# That way, each version is deployed by the deployment script that ships with
# it.

from contextlib import contextmanager
import os
from os import O_CREAT, O_EXCL, remove
from os.path import join, realpath
from pipes import quote
from shutil import rmtree
from subprocess import check_output
from tempfile import mkdtemp, gettempdir
from time import sleep, strftime

from click import command, option, Path
from flask import current_app
import requests

from dxr.app import make_app
from dxr.cli.utils import config_option
from dxr.es import filtered_query_hits, TREE
from dxr.utils import cd, file_text, rmtree_if_exists


@command()
@config_option
@option('-b', '--base',
        'base_path',
        type=Path(exists=True, file_okay=False, resolve_path=True),
        help='Path to the dir containing the builds and symlinks to the '
             'current builds of each kind')
@option('-p', '--python',
        'python_path',
        type=Path(exists=True, dir_okay=False, resolve_path=True),
        help='Path to the Python executable on which to base the virtualenvs')
@option('-e', '--repo',
        help='URL of the git repo from which to download DXR. Use HTTPS if '
             'possible to ward off spoofing.')
@option('-r', '--rev',
        'manual_rev',
        help='A hash of the revision to deploy. Defaults to the last '
             'successful CI build on master.')
@option('-k', '--kind',
        default='prod',
        help='A token distinguishing an independent installation of DXR. 2 '
             'deploy jobs of the same kind will never run simultaneously. '
             'The deployment symlink contains the kind in its name.')
def deploy(**kwargs):
    """Deploy a new version of the web app.

    This should NOT be used to update the copy of DXR run by the indexers, as
    this bails out if not all indexed trees have been built under the latest
    format version.

    This may choose not to deploy for in various cases: for example, if the
    latest version is already deployed. In this cases, a reason is logged to
    stdout. Unanticipated, more serious errors will go to stderr. Thus, you
    can use shell redirects to run this as a cron job and not get too many
    mails, while still having a log file to examine when something goes wrong:

        dxr deploy 1>>some_log_file

    """
    non_none_options = dict((k, v) for k, v in kwargs.iteritems() if v)
    Deployment(**non_none_options).deploy_if_appropriate()


class Deployment(object):
    """A little inversion-of-control framework for deployments

    Maybe someday we'll plug in methods to handle a different project.

    """
    def __init__(self,
                 config,
                 kind='prod',
                 base_path='/data',
                 python_path='/usr/bin/python2.7',
                 repo='https://github.com/mozilla/dxr.git',
                 manual_rev=None):
        """Construct.

        :arg config: The Config
        :arg kind: The type of deployment this is, like "staging" or "prod".
            Affects only the lockfile name.
        :arg base_path: Path to the dir containing the builds and
            deployment links
        :arg python_path: Path to the Python executable on which to base the
            virtualenvs
        :arg repo: URL of the git repo from which to download DXR. Use HTTPS if
            possible to ward off spoofing.
        :arg manual_rev: A hash of the revision to deploy. Defaults to the last
            successful CI build on master.
        """
        self.config = config
        self.kind = kind
        self.base_path = base_path
        self.python_path = python_path
        self.repo = repo
        self.manual_rev = manual_rev

    def rev_to_deploy(self):
        """Return the VCS revision identifier of the version we should
        deploy.

        If we shouldn't deploy for some reason (like if we're already at the
        newest revision or nobody has pressed the Deploy button since the last
        deploy), raise ShouldNotDeploy.

        """
        with cd(join(self._deployment_path(), 'dxr')):
            old_hash = run('git rev-parse --verify HEAD').strip()
        new_hash = self.manual_rev or self._latest_successful_build()
        if old_hash == new_hash:
            raise ShouldNotDeploy('Version %s is already deployed.' % new_hash)
        return new_hash

    def _latest_successful_build(self):
        """Return the SHA of the latest test-passing commit on master."""
        response = requests.get('https://api.github.com/repos/mozilla/dxr/git/'
                                'refs/heads/ci',
                                verify=True)
        try:
            return response.json()['object']['sha']
        except ValueError:
            raise ShouldNotDeploy("Couldn't decode JSON from GitHub API.")

    def build(self, rev):
        """Create and return the path of a new directory containing a new
        deployment of the given revision of the source.

        If it turns out we shouldn't deploy this build after all (perhaps
        because some additional data yielded by an asynchronous build process
        isn't yet available in the new format) but there hasn't been a
        programming error that would warrant a more serious exception, raise
        ShouldNotDeploy.

        """
        VENV_NAME = 'virtualenv'
        new_build_path = mkdtemp(prefix='%s-' % rev[:6],
                                 dir=join(self.base_path, 'builds'))
        try:
            with cd(new_build_path):
                # Make a fresh, blank virtualenv:
                run('virtualenv -p {python} --no-site-packages {venv_name}',
                    python=self.python_path,
                    venv_name=VENV_NAME)

                # Check out the source, and install DXR and dependencies:
                run('git clone {repo} 2>/dev/null', repo=self.repo)
                with cd('dxr'):
                    run('git checkout -q {rev}', rev=rev)

                    old_format = file_text('%s/dxr/dxr/format' % self._deployment_path()).rstrip()
                    new_format = file_text('dxr/format').rstrip()
                    self._format_changed_from = (old_format
                                                 if old_format != new_format
                                                 else None)
                    self._check_deployed_trees(old_format, new_format)

                    run('git submodule update -q --init --recursive')
                    # Make sure a malicious server didn't slip us a mickey. TODO:
                    # Does this recurse into submodules?
                    run('git fsck --no-dangling')

                    # Install stuff, using the new copy of peep from the checkout:
                    venv = join(new_build_path, VENV_NAME)
                    run('VIRTUAL_ENV={venv} make requirements', venv=venv)
                    # Compile nunjucks templates and cachebust static assets:
                    run('make static &> /dev/null')
                    run('{pip} install --no-deps .',
                        pip=join(venv, 'bin', 'pip'))

                # After installing, you always have to re-run this, even if we
                # were reusing a venv:
                run('virtualenv --relocatable {venv}', venv=venv)

                run('chmod 755 .')  # mkdtemp uses a very conservative mask.
        except Exception:
            rmtree(new_build_path)
            raise
        return new_build_path

    def _check_deployed_trees(self, old_format, new_format):
        """Raise ShouldNotDeploy iff we'd be losing currently available
        indices by deploying."""
        olds = self._tree_names_of_version(old_format)
        news = self._tree_names_of_version(new_format)
        olds_still_wanted = set(self.config.trees.iterkeys()) & olds
        not_done = olds_still_wanted - news
        if not_done:
            # There are still some wanted trees that aren't built in the new
            # format yet.
            raise ShouldNotDeploy(
                'We need to wait for trees {trees} to be built in format '
                '{format}.'.format(trees=', '.join(sorted(not_done)),
                                   format=new_format))

    def _tree_names_of_version(self, version):
        """Return a set of the names of trees of a given format version."""
        return set(t['_source']['name'] for t in
                   self._trees_of_version(version))

    def _trees_of_version(self, version):
        """Return an iterable of tree docs of a given format version."""
        return filtered_query_hits(self.config.es_catalog_index,
                                   TREE,
                                   {'format': version},
                                   size=10000)

    def install(self, new_build_path):
        """Install a build at ``self.deployment_path``, and return the path to
        the build we replaced.

        Avoid race conditions as much as possible. If it turns out we should
        not deploy for some anticipated reason, raise ShouldNotDeploy.

        """
        old_build_path = realpath(self._deployment_path())
        with cd(new_build_path):
            run('ln -s {points_to} {sits_at}',
                points_to=new_build_path,
                sits_at='new-link')
            # Big, fat atomic (as in nuclear) mv:
            run('mv -T new-link {dest}', dest=self._deployment_path())
            # Just frobbing the symlink counts as touching the wsgi file.
        return old_build_path

    def delete_old(self, old_build_path):
        """Delete all indices and catalog entries of old format."""

        # A sleep loop around deleting the old build dir. It can take a few
        # seconds for the web servers to restart and relinquish their holds on
        # the shared libs in the old virtualenv. Until that happens, NFS
        # creates .nfs* files in the dir that get in the way of deletion.
        for duration in [1, 5, 10, 30]:
            try:
                rmtree_if_exists(old_build_path)  # doesn't resolve symlinks
            except OSError as exc:
                sleep(duration)
            else:
                break

        if self._format_changed_from:
            # Loop over the trees, get the alias of each, and delete:
            for tree in self._trees_of_version(self._format_changed_from):
                # Do one at a time, because it could be more than a URL's
                # max length, assuming netty has one.
                current_app.es.delete_index(tree['_source']['es_alias'])

                # Delete as we go in case we fail partway through. Then at
                # least we can come back with `dxr delete` and clean up.
                current_app.es.delete(self.config.es_catalog_index,
                                      TREE,
                                      tree['_id'])

    def deploy_if_appropriate(self):
        """Deploy a new build if we should."""
        with nonblocking_lock('dxr-deploy-%s' % self.kind) as got_lock:
            if got_lock:
                with make_app(self.config).app_context():
                    try:
                        rev = self.rev_to_deploy()
                        new_build_path = self.build(rev)
                        old_build_path = self.install(new_build_path)
                    except ShouldNotDeploy as exc:
                        log(exc)
                    else:
                        # if not self.passes_smoke_test():
                        #     self.rollback()
                        # else:
                        self.delete_old(old_build_path)
                        log('Deployed revision %s.' % (rev,))

    def _deployment_path(self):
        """Return the path of the symlink to the deployed build of DXR."""
        return join(self.base_path, 'dxr-%s' % self.kind)


def log(message):
    print strftime('%Y-%m-%d %H:%M:%S'), message


def run(command, **kwargs):
    """Return the output of a command.

    Pass in any kind of shell-executable line you like, with one or more
    commands, pipes, etc. Any kwargs will be shell-escaped and then subbed into
    the command using ``format()``::

        >>> run('echo hi')
        "hi"
        >>> run('echo {name}', name='Fred')
        "Fred"

    This is optimized for callsite readability. Internalizing ``format()``
    keeps noise off the call. If you use named substitution tokens, individual
    commands are almost as readable as in a raw shell script. The command
    doesn't need to be read out of order, as with anonymous tokens.

    """
    output = check_output(
        command.format(**dict((k, quote(v)) for k, v in kwargs.iteritems())),
        shell=True)
    return output


@contextmanager
def nonblocking_lock(lock_name):
    """Context manager that acquires and releases a file-based lock.

    If it cannot immediately acquire it, it falls through and returns False.
    Otherwise, it returns True.

    """
    lock_path = join(gettempdir(), lock_name + '.lock')
    try:
        fd = os.open(lock_path, O_CREAT | O_EXCL, 0644)
    except OSError:
        got = False
    else:
        got = True

    try:
        yield got
    finally:
        if got:
            os.close(fd)
            remove(lock_path)


class ShouldNotDeploy(Exception):
    """We should not deploy this build at the moment, though there was no
    programming error."""

    def __str__(self):
        return 'Did not deploy. %s' % (self.args[0],)
