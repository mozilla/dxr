from commands import getstatusoutput
import json
from os import chdir, mkdir
import os.path
from os.path import dirname
from shutil import rmtree
import sys
from tempfile import mkdtemp
import unittest
from urllib2 import quote

from nose.tools import eq_

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


class TestCase(unittest.TestCase):
    """Container for general convenience functions for DXR tests"""

    def client(self):
        # TODO: DRY between here and the config file with 'target'.
        app = make_app(os.path.join(self._instance_path, 'target'))

        app.config['TESTING'] = True  # Disable error trapping during requests.
        return app.test_client()

    def found_files_eq(self, query, filenames):
        """Assert that executing the search ``query`` finds the paths
        ``filenames``."""
        paths = set(result['path'] for result in self.search_results(query))
        eq_(paths, set(filenames))

    def found_line_eq(self, query, content, line):
        """Assert that a query returns a single file and single matching line
        and that its line number and content are as expected, modulo leading
        and trailing whitespace.

        This is a convenience function for searches that return only one
        matching file and only one line within it so you don't have to do a
        zillion dereferences in your test.

        """
        self.found_lines_eq(query, [(content, line)])

    def found_lines_eq(self, query, success_lines):
        """Assert that a query returns a single file and that the highlighted
        lines are as expected, modulo leading and trailing whitespace."""
        results = self.search_results(query)
        num_results = len(results)
        eq_(num_results, 1, msg='Query passed to found_lines_eq() returned '
                                 '%s files, not one.' % num_results)
        lines = results[0]['lines']
        eq_([(line['line'].strip(), line['line_number']) for line in lines],
            success_lines)

    def found_nothing(self, query):
        """Assert that a query returns no hits."""
        results = self.search_results(query)
        eq_(results, [])

    def search_results(self, query):
        """Return the raw results of a JSON search query.

        Example::

          [
            {
              "path": "main.c",
              "lines": [
                {
                  "line_number": 7,
                  "line": "int <b>main</b>(int argc, char* argv[]) {"
                }
              ],
              "icon": "mimetypes/c"
            }
          ]

        """
        response = self.client().get(
            '/search?format=json&tree=code&q=%s&redirect=false' % quote(query))
        return json.loads(response.data)['results']


class DxrInstanceTestCase(TestCase):
    """Test case which builds an actual DXR instance that lives on the
    filesystem and then runs its tests

    This is suitable for complex tests with many files where the FS is the
    least confusing place to express them.

    """
    @classmethod
    def setup_class(cls):
        """Build the instance."""
        # nose does some amazing magic that makes this work even if there are
        # multiple test modules with the same name:
        cls._instance_path = dirname(sys.modules[cls.__module__].__file__)
        chdir(cls._instance_path)
        run('make')

    @classmethod
    def teardown_class(cls):
        chdir(cls._instance_path)
        run('make clean')


class SingleFileTestCase(TestCase):
    """Container for tests that need only a single source file

    You can express the source as a string rather than creating a whole bunch
    of files in the FS. I'll slam it down into a temporary DXR instance and
    then kick off the usual build process, deleting the instance afterward.

    """
    # Set this to False in a subclass to keep the generated instance around and
    # print its path so you can examine it:
    should_delete_instance = True

    @classmethod
    def setup_class(cls):
        """Create a temporary DXR instance on the FS, and build it."""
        cls._instance_path = mkdtemp()
        code_path = os.path.join(cls._instance_path, 'code')
        mkdir(code_path)
        _make_file(code_path, 'main.cpp', cls.source)
        # $CXX gets injected by the clang DXR plugin:
        _make_file(cls._instance_path, 'dxr.config', """
[DXR]
enabled_plugins = pygmentize clang
temp_folder = {instance_path}/temp
target_folder = {instance_path}/target
nb_jobs = 4

[code]
source_folder = {instance_path}/code
object_folder = {instance_path}/code
build_command = $CXX -o main main.cpp

[Template]
foot_text =
""".format(instance_path=cls._instance_path))

        chdir(cls._instance_path)
        run('dxr-build.py')

    @classmethod
    def teardown_class(cls):
        if cls.should_delete_instance:
            rmtree(cls._instance_path)
        else:
            print 'Not deleting instance %s.' % cls._instance_path

    def found_line_eq(self, query, content, line=None):
        """A specialization of ``found_line_eq`` that computes the line number
        if not given

        :arg line: The expected line number. If omitted, we'll compute it,
            given a match for ``content`` (minus ``<b>`` tags) in
            ``self.source``.

        """
        if not line:
            line = self.source.count( '\n', 0, self.source.index(
                content.replace('<b>', '').replace('</b>', ''))) + 1
        super(SingleFileTestCase, self).found_line_eq(query, content, line)



def _make_file(path, filename, contents):
    """Make file ``filename`` within ``path``, full of unicode ``contents``."""
    with open(os.path.join(path, filename), 'w') as file:
        file.write(contents.encode('utf-8'))


# Tests that don't otherwise need a main() can append this one just to get
# their code to compile:
MINIMAL_MAIN = """
    int main(int argc, char* argv[]) {
        return 0;
    }
    """
