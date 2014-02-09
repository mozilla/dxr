"""Continuous deployment script for DXR

Glossary
========

build directory - A folder, typically in the ``builds`` folder, containing
    these folders...

    dxr - A checkout of the DXR source code
    target - A symlink to the instance to serve
    virtualenv - A virtualenv with DXR and its dependencies installed

    Builds are named after an excerpt of their git hashes and are symlinked
    into the base directory.

base directory - The folder containing these folders...

    builds - A folder of builds, including the current production and staging
        ones
    dxr-prod - A symlink to the current production build
    dxr-staging - A symlink to the current staging build
    instances - A folder of DXR instances organized according to format version

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
from optparse import OptionParser
import os
from os import chdir, O_CREAT, O_EXCL, remove, getcwd
from os.path import join, exists
from pipes import quote
from subprocess import check_output
from tempfile import mkdtemp, gettempdir

import requests


def main():
    """Handle command-line munging, and pass off control to the interesting
    stuff."""
    parser = OptionParser(
        usage='usage: %prog [options] <staging | prod>',
        description='Deploy a new version of DXR.')
    parser.add_option('-b', '--base', dest='base_path',
                      help='Path to the dir containing the builds, instances, '
                           'and deployment links')
    parser.add_option('-c', '--branch', dest='branch',
                      help='Deploy the revision from this branch which last '
                           'passed Jenkins.')
    parser.add_option('-p', '--python', dest='python_path',
                      help='Path to the Python executable on which to base the'
                           ' virtualenvs')
    parser.add_option('-e', '--repo', dest='repo',
                      help='URL of the git repo from which to download DXR. '
                           'Use HTTPS if possible to ward off spoofing.')
    parser.add_option('-r', '--rev', dest='manual_rev',
                      help='A hash of the revision to deploy. Defaults to the '
                           'last successful Jenkins build on the branch '
                           'specified by -c (or master, by default).')

    options, args = parser.parse_args()
    if len(args) == 1:
        non_none_options = dict((k, getattr(options, k)) for k in
                                (o.dest for o in parser.option_list if o.dest)
                                if getattr(options, k))
        Deployment(args[0], **non_none_options).deploy_if_appropriate()
    else:
        parser.print_usage()


class Deployment(object):
    """A little inversion-of-control framework for deployments

    Maybe someday we'll plug in methods to handle a different project.

    """
    def __init__(self,
                 kind,
                 base_path='/data',
                 python_path='/usr/bin/python2.7',
                 repo='https://github.com/mozilla/dxr.git',
                 branch='master',
                 manual_rev=None):
        """Construct.

        :arg kind: The type of deployment this is, either "staging" or "prod".
            Affects only some folder names.
        :arg base_path: Path to the dir containing the builds, instances, and
            deployment links
        :arg python_path: Path to the Python executable on which to base the
            virtualenvs
        :arg repo: URL of the git repo from which to download DXR. Use HTTPS if
            possible to ward off spoofing.
        :arg branch: The most recent passing Jenkins build from this branch
            will be deployed by default.
        :arg manual_rev: A hash of the revision to deploy. Defaults to the last
            successful Jenkins build on ``branch``.
        """
        self.kind = kind
        self.base_path = base_path
        self.python_path = python_path
        self.repo = repo
        self.branch = branch
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
        new_hash = self._latest_successful_build()
        if old_hash == new_hash:
            raise ShouldNotDeploy('The latest test-passing revision is already'
                                  ' deployed.')
        return new_hash

    def _latest_successful_build(self):
        """Return the SHA of the latest test-passing commit on master."""
        response = requests.get('https://ci.mozilla.org/job/dxr/'
                                'lastSuccessfulBuild/git/api/json',
                                verify=True)
        return (response.json()['buildsByBranchName']
                               ['origin/%s' % self.branch]
                               ['revision']
                               ['SHA1'])

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
        with cd(new_build_path):
            # Make a fresh, blank virtualenv:
            run('virtualenv -p {python} --no-site-packages {venv_name}',
                python=self.python_path,
                venv_name=VENV_NAME)

            # Check out the source, and install DXR and dependencies:
            run('git clone {repo}', repo=self.repo)
            with cd('dxr'):
                run('git checkout -q {rev}', rev=rev)

                # If there's no instance of a suitable version, bail out:
                with open('format') as format_file:
                    format = format_file.read().rstrip()
                target_path = '{base_path}/instances/{format}/target'.format(
                    base_path=self.base_path, format=format)
                if not exists(target_path):
                    raise ShouldNotDeploy('A version-{format} instance is not ready yet.'.format(format=format))

                run('git submodule update -q --init --recursive')
                # Make sure a malicious server didn't slip us a mickey. TODO:
                # Does this recurse into submodules?
                run('git fsck --no-dangling')

                # Install stuff, using the new copy of peep from the checkout:
                python = join(new_build_path, VENV_NAME, 'bin', 'python')
                run('{python} ./peep.py install -r requirements.txt',
                    python=python)
                # Quiet the complaint about there being no matches for *.so:
                run('{python} setup.py install 2>/dev/null', python=python)

            # After installing, you always have to re-run this, even if we
            # were reusing a venv:
            run('virtualenv --relocatable {venv}',
                venv=join(new_build_path, VENV_NAME))

            # Link to the built DXR instance:
            run('ln -s {points_to} target', points_to=target_path)

            run('chmod 755 .')  # mkdtemp uses a very conservative mask.
        return new_build_path

    def install(self, new_build_path):
        """Install a build at ``self.deployment_path``.

        Avoid race conditions as much as possible. If it turns out we should
        not deploy for some anticipated reason, raise ShouldNotDeploy.

        """
        with cd(new_build_path):
            run('ln -s {points_to} {sits_at}',
                points_to=new_build_path,
                sits_at='new-link')
            # Big, fat atomic (nay, nuclear) mv:
            run('mv -T new-link {dest}', dest=self._deployment_path())
        # TODO: Delete the old build or maybe all the builds that aren't this
        # one or the previous one (which we can get by reading the old symlink).

        # TODO: Does just frobbing the symlink count as touching the wsgi file?

    def deploy_if_appropriate(self):
        """Deploy a new build if we should."""
        with nonblocking_lock('dxr-deploy-%s' % self.kind) as got_lock:
            if got_lock:
                try:
                    rev = self.manual_rev or self.rev_to_deploy()
                    new_build_path = self.build(rev)
                    self.install(new_build_path)
                except ShouldNotDeploy:
                    pass
                else:
                    # if not self.passes_smoke_test():
                    #     self.rollback()
                    pass

    def _deployment_path(self):
        """Return the path of the symlink to the deployed build of DXR."""
        return join(self.base_path, 'dxr-%s' % self.kind)


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
def cd(path):
    """Change the working dir on enter, and change it back on exit."""
    old_dir = getcwd()
    chdir(path)
    yield
    chdir(old_dir)


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


if __name__ == '__main__':
    main()
