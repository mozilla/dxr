import cgi
from commands import getoutput
import json
from os import chdir, mkdir
from os.path import dirname, join, sep
import re
from shutil import rmtree
import subprocess
import sys
from tempfile import mkdtemp
import unittest

from flask import url_for
from nose.tools import eq_, ok_
from pyelasticsearch import ElasticSearch

try:
    from nose.tools import assert_in
except ImportError:
    def assert_in(item, container, msg=None):
        ok_(item in container, msg=msg or '%r not in %r' % (item, container))

from dxr.app import make_app
from dxr.build import index_and_deploy_tree
from dxr.config import Config
from dxr.utils import file_text, run


class TestCase(unittest.TestCase):
    """Abstract container for general convenience functions for DXR tests"""

    def client(self):
        self._app = make_app(self.config())
        self._app.config['TESTING'] = True  # Disable error trapping during requests.
        return self._app.test_client()

    def url_for(self, *args, **kwargs):
        """Do the magic needed to make url_for() work under tests."""
        with self._app.test_request_context():
            return url_for(*args, **kwargs)

    @classmethod
    def config(cls):
        return Config(cls.config_input(cls._config_dir_path),
                      relative_to=cls._config_dir_path)

    def source_page(self, path):
        """Return the text of a source page."""
        return self.client().get('/code/source/%s' % path).data

    def found_files(self, query, is_case_sensitive=True):
        """Return the set of paths of files found by a search query."""
        return set(sep.join(result['path']).replace('<b>', '').replace('</b>', '') for result in
                   self.search_results(query,
                                       is_case_sensitive=is_case_sensitive))

    def found_files_eq(self, query, filenames, is_case_sensitive=True):
        """Assert that executing the search ``query`` finds the paths
        ``filenames``."""
        eq_(self.found_files(query,
                             is_case_sensitive=is_case_sensitive),
            set(filenames))

    def found_line_eq(self, query, content, line, is_case_sensitive=True):
        """Assert that a query returns a single file and single matching line
        and that its line number and content are as expected, modulo leading
        and trailing whitespace.

        This is a convenience function for searches that return only one
        matching file and only one line within it so you don't have to do a
        zillion dereferences in your test.

        """
        self.found_lines_eq(query,
                            [(content, line)],
                            is_case_sensitive=is_case_sensitive)

    def found_lines_eq(self, query, expected_lines, is_case_sensitive=True):
        """Assert that a query returns a single file and that the highlighted
        lines are as expected, modulo leading and trailing whitespace."""
        results = self.search_results(query,
                                      is_case_sensitive=is_case_sensitive)
        num_results = len(results)
        eq_(num_results, 1, msg='Query passed to found_lines_eq() returned '
                                 '%s files, not one.' % num_results)
        lines = results[0]['lines']
        eq_([(line['line'].strip(), line['line_number']) for line in lines],
            expected_lines)

    def found_nothing(self, query, is_case_sensitive=True):
        """Assert that a query returns no hits."""
        results = self.search_results(query,
                                      is_case_sensitive=is_case_sensitive)
        eq_(results, [])

    def search_response(self, query, is_case_sensitive=True):
        """Return the raw response of a JSON search query."""
        return self.client().get(
            self.url_for('.search',
                         tree='code',
                         q=query,
                         redirect='false',
                         case='true' if is_case_sensitive else 'false'),
            headers={'Accept': 'application/json'})

    def direct_result_eq(self, query, path, line_number, is_case_sensitive=True):
        """Assert that a direct result exists and takes the user to the given
        path at the given line number.

        If line_number is None, assert we point to no particular line number.

        """
        response = self.client().get(
            self.url_for('.search',
                         tree='code',
                         q=query,
                         redirect='true',
                         case='true' if is_case_sensitive else 'false'),
            headers={'Accept': 'application/json'})
        eq_(response.status_code, 200)
        try:
            location = json.loads(response.data)['redirect']
        except KeyError:
            self.fail("The query didn't return a direct result.")
        eq_(location[:location.index('?')], '/code/source/' + path)
        if line_number is None:
            # When line_number is None, assert we point to a file in general,
            # not to a particular line number:
            ok_('#' not in location)
        else:
            # Location is something like
            # /code/source/main.cpp?from=main.cpp:6&case=true#6.
            eq_(int(location[location.index('#') + 1:]), line_number)

    def is_not_direct_result(self, query):
        """Assert that running a query results in a normal set of results,
        possibly empty, as opposed to a direct result that redirects."""
        response = self.client().get(
            self.url_for('.search',
                         tree='code',
                         q=query,
                         redirect='true',
                         case='true'),
            headers={'Accept': 'application/json'})
        eq_(response.status_code, 200)
        ok_('redirect' not in json.loads(response.data))

    def search_results(self, query, is_case_sensitive=True):
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
        response = self.search_response(query,
                                        is_case_sensitive=is_case_sensitive)
        data = json.loads(response.data)
        return data['promoted'] + data['results']

    def clang_at_least(self, version):
        output = getoutput("clang --version")
        if not output:
            return False
        # search() rather than match() because Ubuntu changes the version
        # string to be "Ubuntu clang version 3.5", for instance:
        match = re.search('clang version ([0-9]+\.[0-9]+)', output)
        if not match:
            return False
        return float(match.group(1)) >= version

    @classmethod
    def _es(cls):
        return ElasticSearch('http://127.0.0.1:9200/')

    @classmethod
    def _delete_es_indices(cls):
        """Delete anything that is named like a DXR test index.

        Yes, this is scary as hell but very expedient. Won't work if
        ES's action.destructive_requires_name is set to true.

        """
        # When you delete an index, any alias to it goes with it.
        # This takes care of dxr_test_catalog as well.
        cls._es().delete_index('dxr_test_*')


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
        cls._config_dir_path = dirname(sys.modules[cls.__module__].__file__)
        chdir(cls._config_dir_path)
        run('dxr index')
        cls._es().refresh()

    @classmethod
    def teardown_class(cls):
        chdir(cls._config_dir_path)
        cls._delete_es_indices()  # TODO: Replace with a call to 'dxr delete --force'.
        run('dxr clean')

    @classmethod
    def config_input(cls, config_dir_path):
        return file_text(join(cls._config_dir_path, 'dxr.config'))


class DxrInstanceTestCaseMakeFirst(DxrInstanceTestCase):
    """Test case which runs `make` before dxr index and `make clean` before dxr
    clean within a code directory, and otherwise delegates to DxrInstanceTestCase.

    This test is suitable for cases where some setup must be performed before
    `dxr index` can be run (for example extracting sources from archive).

    """
    @classmethod
    def setup_class(cls):
        build_dir = join(dirname(sys.modules[cls.__module__].__file__), 'code')
        subprocess.check_call(['make'], cwd=build_dir)
        super(DxrInstanceTestCaseMakeFirst, cls).setup_class()

    @classmethod
    def teardown_class(cls):
        build_dir = join(dirname(sys.modules[cls.__module__].__file__), 'code')
        subprocess.check_call(['make', 'clean'], cwd=build_dir)
        super(DxrInstanceTestCaseMakeFirst, cls).teardown_class()


class SingleFileTestCase(TestCase):
    """Container for tests that need only a single source file

    You can express the source as a string rather than creating a whole bunch
    of files in the FS. I'll slam it down into a temporary DXR instance and
    then kick off the usual build process, deleting the instance afterward.

    """
    # Set this to True in a subclass to keep the generated instance around and
    # host it on port 8000 so you can examine it:
    stop_for_interaction = False

    # Override this in a subclass to change the filename used for the
    # source file.
    source_filename = 'main.cpp'

    @classmethod
    def setup_class(cls):
        """Create a temporary DXR instance on the FS, and build it."""
        cls._config_dir_path = mkdtemp()
        code_path = join(cls._config_dir_path, 'code')
        mkdir(code_path)
        _make_file(code_path, cls.source_filename, cls.source)

        for tree in cls.config().trees.itervalues():
            index_and_deploy_tree(tree)
        cls._es().refresh()

    @classmethod
    def config_input(cls, config_dir_path):
        """Return a dictionary of config options for building the tree.

        Override this in subclasses to customize the config.
        """
        return {
            'DXR': {
                'enabled_plugins': 'pygmentize clang',
                'temp_folder': '{0}/temp'.format(config_dir_path),
                'es_index': 'dxr_test_{format}_{tree}_{unique}',
                'es_alias': 'dxr_test_{format}_{tree}',
                'es_catalog_index': 'dxr_test_catalog'
            },
            'code': {
                'source_folder': '{0}/code'.format(config_dir_path),
                'object_folder': '{0}/code'.format(config_dir_path),
                'build_command': '$CXX -o main main.cpp'
            }
        }

    @classmethod
    def teardown_class(cls):
        if cls.stop_for_interaction:
            print "Pausing for interaction at 0.0.0.0:8000..."
            make_app(cls.config()).run(host='0.0.0.0', port=8000)
            print "Cleaning up indices..."
        cls._delete_es_indices()
        rmtree(cls._config_dir_path)

    def _source_for_query(self, s):
        return (s.replace('<b>', '')
                 .replace('</b>', '')
                 .replace('&lt;', '<')
                 .replace('&gt;', '>')
                 .replace('&quot;', '"')
                 .replace('&amp;', '&'))

    def _guess_line(self, content):
        """Take a guess at which line number of our source code some (possibly
        highlighted) content is from.

        """
        return self.source.count(
                '\n',
                0,
                self.source.index(self._source_for_query(content))) + 1

    def found_line_eq(self, query, content, line=None, is_case_sensitive=True):
        """A specialization of ``found_line_eq`` that computes the line number
        if not given

        :arg line: The expected line number. If omitted, we'll compute it,
            given a match for ``content`` (minus ``<b>`` tags) in
            ``self.source``.

        """
        if not line:
            line = self._guess_line(content)
        super(SingleFileTestCase, self).found_line_eq(
                query, content, line, is_case_sensitive=is_case_sensitive)

    def found_lines_eq(self, query, expected_lines, is_case_sensitive=True):
        """A specialization of ``found_lines_eq`` that computes the line
        numbers if not given

        :arg expected_lines: A list of pairs (line content, line number) or
            strings (just line content) specifying expected results

        """
        def to_pair(line):
            """Take either a string (a line of source, optionally highlit) or
            a pair of (line of source, line number), and return (line of
            source, line number).

            """
            if isinstance(line, basestring):
                return line, self._guess_line(line)
            return line

        expected_pairs = map(to_pair, expected_lines)
        super(SingleFileTestCase, self).found_lines_eq(
                query, expected_pairs, is_case_sensitive=is_case_sensitive)

    def direct_result_eq(self, query, line_number, is_case_sensitive=True):
        """Assume the filename "main.cpp"."""
        return super(SingleFileTestCase, self).direct_result_eq(query, 'main.cpp', line_number, is_case_sensitive=is_case_sensitive)


def _make_file(path, filename, contents):
    """Make file ``filename`` within ``path``, full of unicode ``contents``."""
    with open(join(path, filename), 'w') as file:
        file.write(contents.encode('utf-8'))


# Tests that don't otherwise need a main() can append this one just to get
# their code to compile:
MINIMAL_MAIN = """
    int main(int argc, char* argv[]) {
        return 0;
    }
    """


def _decoded_menu_on(haystack, text):
    """Return the JSON-decoded menu found around the source code ``text`` in
    the HTML ``haystack``.

    Raise an AssertionError if there is no menu there.

    """
    # We just use cheap-and-cheesy regexes for now, to avoid pulling in and
    # compiling the entirety of lxml to run pyquery.
    match = re.search(
            '<a data-menu="([^"]+)"[^>]*>' + re.escape(cgi.escape(text)) + '</a>',
            haystack)
    if match:
        return json.loads(match.group(1).replace('&quot;', '"')
                                        .replace('&lt;', '<')
                                        .replace('&gt;', '>')
                                        .replace('&amp;', '&'))
    else:
        ok_(False, "No menu around '%s' was found." % text)


def menu_on(haystack, text, *menu_items):
    """Assert that there is a context menu on certain text that contains
    certain menu items.

    :arg haystack: The HTML source of a page to search
    :arg text: The text contained by the menu's anchor tag. The first
        menu-having anchor tag containing the text is the one compared against.
    :arg menu_items: Dicts whose pairs must be contained in some item of the
        menu. If an item is found to match, it is discarded can cannot be
        reused to match another element of ``menu_items``.

    """
    def removed_match(expected, found_items):
        """Remove the first menu item from ``found_items`` where the keys in
        ``expected`` match it. If none is found, return False; else, True.

        :arg expected: Dict whose pairs are expected to be found in an item of
            ``found_items``
        :arg found_items: A list of dicts representing menu items actually on
            the page

        """
        def matches(expected, found):
            """Return whether all the pairs in ``expected`` are found in
            ``found``.

            """
            for k, v in expected.iteritems():
                if found.get(k) != v:
                    return False
            return True

        for i, found in enumerate(found_items):
            if matches(expected, found):
                del found_items[i]
                return True
        return False

    found_items = _decoded_menu_on(haystack, text)
    for expected in menu_items:
        removed = removed_match(expected, found_items)
        if not removed:
            ok_(False, "No menu item with the keys %r was found in the menu around '%s'." % (expected, text))


def menu_item_not_on(haystack, text, menu_item_html):
    """Assert that there is a context menu on certain text that doesn't
    contain a given menu item.

    :arg haystack: The HTML source of a page to search
    :arg text: The text contained by the menu's anchor tag. The first
        menu-having anchor tag containing the text is the one compared against.
    :arg menu_item_html: The title of a menu item that should be missing from
        the menu, given in HTML

    """
    found_items = _decoded_menu_on(haystack, text)
    ok_(all(menu_item_html != item['html'] for item in found_items),
        '"%s" was found in the menu around "%s".' % (menu_item_html, text))
