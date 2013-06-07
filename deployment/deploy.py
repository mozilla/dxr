"""Continuous deployment script for DXR

Glossary
========

build directory - A folder containing these folders...

    dxr - A checkout of the DXR source code
    target - A symlink to the instance to serve
    virtualenv - A virtualenv with DXR and its dependencies installed

    Builds are named after an excerpt of their git hashes and are symlinked
    into the deployment directory.

deployment directory - The folder containing these folders...

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

from contextlib import contextmanager
from optparse import OptionParser
import os
from os import chdir, O_CREAT, O_EXCL
from os.path import join
from pipes import quote
from subprocess import check_output
from tempfile import mkdtemp, gettempdir

import requests


def main():
    """Handle command-line munging, and pass off control to the interesting
    stuff."""
    parser = OptionParser(
        usage='usage: %prog <staging | prod>',
        description='Deploy a new version of DXR.')
    options, args = parser.parse_args()
    try:
        Deployment(*args).deploy_if_appropriate()
    except TypeError:  # wrong number of args
        parser.print_usage()


class Deployment(object):
    """A little inversion-of-control framework for deployments

    Maybe someday we'll plug in methods to handle a different project.

    """
    def __init__(self, kind):
        self.kind = kind

    def rev_to_deploy(self):
        """Return the VCS revision identifier of the version we should
        deploy.

        If we shouldn't deploy for some reason (like if we're already at the
        newest revision or nobody has pressed the Deploy button since the last
        deploy), raise ShouldNotDeploy.

        """
        def latest_successful_build():
            """Return the SHA of the latest test-passing commit on master."""
            response = requests.get('https://ci.mozilla.org/job/dxr/'
                                    'lastSuccessfulBuild/git/api/json',
                                    verify=True)
            return (response.json()['buildByBranchName']
                                   ['origin/master']
                                   ['revision']
                                   ['SHA1'])
        with cd(self._deployment_path()):
            old_hash = run('git rev-parse --verify HEAD')
        new_hash = latest_successful_build()
        if old_hash == new_hash:
            raise ShouldNotDeploy('The latest test-passing revision is already'
                                  ' deployed.')
        return new_hash

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
        new_build_path = mkdtemp(prefix='%s-' % rev[:6], dir='/data/builds')
        with cd(new_build_path):
            # Make a fresh, blank virtualenv:
            run('virtualenv -p /usr/bin/python2.7 --no-site-packages {venv_name}',
                venv_name=VENV_NAME)

            # Check out the source, and install DXR and dependencies:
            run('git clone https://github.com/mozilla/dxr.git')
            with cd('dxr'):
                run('git checkout', rev)
                run('git submodule update --init --recursive')
                # Make sure a malicious server didn't slip us a mickey. TODO:
                # Does this recurse into submodules?
                run('git fsck --no-dangling')

                # Install stuff:
                venv_bin_path = join(new_build_path, VENV_NAME, 'bin')
                run('{pip} install -r requirements.txt',
                    pip=join(venv_bin_path, 'pip'))
                run('{python} setup.py install',
                    python=join(venv_bin_path, 'python'))

            # After installing, you always have to re-run this, even if we
            # were reusing a venv:
            run('virtualenv --relocatable {venv}',
                venv=join(new_build_path, VENV_NAME))

            # Link to the built, version-0 DXR instance. TODO: Figure out which
            # instance to use based on the format version embedded in DXR. If
            # there isn't an instance that new yet, raise ShouldNotDeploy.
            run('ln -s {points_to} target',
                points_to='/data/instances/0/target')

            run('chmod 755 .')  # mkdtemp uses a very conservative mask.

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
        with NonblockingLock('dxr-deploy-%s' % self.kind) as got_lock:
            if got_lock:
                try:
                    rev = self.rev_to_deploy()
                    new_build_path = self.build(rev)
                    self.install(new_build_path)
                except ShouldNotDeploy:
                    pass  # TODO: log to stdout or stderr
                else:
                    # if not self.passes_smoke_test():
                    #     self.rollback()
                    pass

    def _deployment_path(self):
        """Return the path of the symlink to the deployed build of DXR."""
        return '/data/dxr-%s' % self.kind


def run(command, **kwargs):
    """Return the output of a command, with any trailing newline stripped.

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
        command.format(dict((k, quote(v)) for k, v in kwargs.iteritems())),
        shell=True)
    if output.endswith('\n'):
        output = output[:-1]
    return output


@contextmanager
def cd(path):
    """Change the working dir on enter, and change it back on exit."""
    old_dir = getcwd()
    chdir(path)
    yield
    chdir(old_dir)


class NonblockingLock(object):
    """Context manager that acquires and releases a file-based lock.

    If it cannot immediately acquire it, it falls through and returns False.
    Otherwise, it returns True.

    """
    def __init__(self, lock_name):
        self.lock_path = join(gettempdir(), lock_name + '.lock')

    def __enter__(self):
        """Return whether we succeeded in acquiring the lock."""
        try:
            self.fd = os.open(self.lock_path, O_CREAT | O_EXCL, 0644)
        except OSError:
            self.fd = None
            return False
        return True

    def __exit__(self, type, value, traceback):
        if self.fd is not None:
            os.close(self.fd)
            remove(self.lock_path)


class ShouldNotDeploy(Exception):
    """We should not deploy this build at the moment, though there was no
    programming error."""


if __name__ == '__main__':
    main()
