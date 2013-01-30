from commands import getstatusoutput
import json
import os.path
from os.path import dirname
import sys
from unittest import TestCase
from urllib2 import quote

try:
    from nose.tools import assert_in
except ImportError:
    from nose.tools import ok_
    def assert_in(item, container, msg=None):
        ok_(item in container, msg=msg or '%r not in %r' % (item, container))

from dxr.app import make_app


# ---- This crap is very temporary: ----


class CommandFailure(Exception):
    """A command exited with a non-zero status code."""

    def __init__(self, command, status, output):
        self.command, self.status, self.output = command, status, output

    def __str__(self):
        return "'%s' exited with status %s. Output:\n%s" % (self.command,
                                                            self.status,
                                                            self.output)


def run(command):
    """Run a shell command, and return its stdout. On failure, raise
    `CommandFailure`.

    """
    status, output = getstatusoutput(command)
    if status:
        raise CommandFailure(command, status, output)
    return output


# ---- More permanent stuff: ----


class DxrInstanceTestCase(TestCase):
    """A pile of tests to be run inside a DXR instance after building it"""

    @classmethod
    def setup_class(cls):
        """Build the instance."""
        # nose does some amazing magic that makes this work even if there are
        # multiple test modules with the same name:
        cls._dir = dirname(sys.modules[cls.__module__].__file__)

        # TODO: Escaping doesn't exist. Replace this use of make altogether
        # (here and in teardown) with Python.
        run("cd '%s' && make" % cls._dir)

    @classmethod
    def teardown_class(cls):
        run("cd '%s' && make clean" % cls._dir)

    def client(self):
        # TODO: DRY between here and the config file with 'target'.
        app = make_app(os.path.join(self._dir, 'target'))

        app.config['TESTING'] = True  # Disable error trapping during requests.
        return app.test_client()

    def assert_query_includes(self, query, included_filenames):
        response = self.client().get(
            '/search?format=json&tree=HelloWorld&q=%s&redirect=false' %
            quote(query))
        paths = [result['path'] for result in
                 json.loads(response.data)['results']]
        for filename in included_filenames:
            assert_in(filename, paths)
