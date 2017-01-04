import cgi
from commands import getoutput
import json
from os import mkdir
from os.path import dirname, join
import re
from shutil import rmtree
from subprocess import check_call
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
from dxr.utils import cd, file_text, run


class TestCase(unittest.TestCase):
    """Basic test harness for DXR

    Provides Flask application context (if you call app()) and various
    convenience functions.

    """
    @classmethod
    def setup_class(cls):
        """Create a temporary DXR instance on the FS, and build it."""
        cls.generate()
        cls.index()
        cls._es().refresh()

    @classmethod
    def teardown_class(cls):
        cls._delete_es_indices()  # TODO: Replace with a call to 'dxr delete --force'.
        cls.degenerate()

    @classmethod
    def generate(cls):
        """Create any on-disk artifacts necessary before running the ``dxr
        index`` job. Squirrel away the config file's dir path in
        ``cls._config_dir_path``."""
        cls._config_dir_path = mkdtemp()

    @classmethod
    def degenerate(cls):
        """Remove any on-disk artifacts created by ``generate()``."""
        rmtree(cls._config_dir_path)

    @classmethod
    def index(cls):
        """Run a DXR indexing job."""

    @classmethod
    def dxr_index(cls):
        """Run the `dxr index` command in the config file's directory."""
        with cd(cls._config_dir_path):
            run('dxr index')

    @classmethod
    def this_dir(cls):
        """Return the path to the dir containing the testcase class."""
        # nose does some amazing magic that makes this work even if there are
        # multiple test modules with the same name:
        return dirname(sys.modules[cls.__module__].__file__)

    @classmethod
    def code_dir(cls):
        """Return the path to the folder which typically contains the indexed
        source code in tests with only one source tree."""
        return join(cls._config_dir_path, 'code')

    def app(self):
        if not hasattr(self, '_app'):
            self._app = make_app(self.config())
            self._app.config['TESTING'] = True  # Disable error trapping during requests.
        return self._app

    def client(self):
        return self.app().test_client()

    def url_for(self, *args, **kwargs):
        """Do the magic needed to make url_for() work under tests."""
        with self.app().test_request_context():
            return url_for(*args, **kwargs)

    @classmethod
    def config(cls):
        return Config(cls.config_input(cls._config_dir_path),
                      relative_to=cls._config_dir_path)

    @classmethod
    def config_input(cls, config_dir_path):
        """Return a dictionary or string of config options for building the
        tree.

        Override this in subclasses to customize the config. This default
        implementation returns just enough to instantiate the Flask app.

        """
        return {
            'DXR': {
                'enabled_plugins': '',
                'temp_folder': '{0}/temp'.format(config_dir_path),
                'es_index': 'dxr_test_{format}_{tree}_{unique}',
                'es_alias': 'dxr_test_{format}_{tree}',
                'es_catalog_index': 'dxr_test_catalog'
            },
            'code': {
                'source_folder': '{0}/code'.format(config_dir_path),
                'build_command': ''
            }
        }

    def source_page(self, path):
        """Return the text of a source page."""
        return self.client().get('/code/source/%s' % path).data

    def found_files(self, query):
        """Return the set of paths of files found by a search query."""
        return set(result['path'] for result in
                   self.search_results(query))

    def found_files_eq(self, query, filenames):
        """Assert that executing the search ``query`` finds the paths
        ``filenames``."""
        eq_(self.found_files(query), set(filenames))

    def found_line_eq(self, query, content, line):
        """Assert that a query returns a single file and single matching line
        and that its line number and content are as expected, modulo leading
        and trailing whitespace.

        This is a convenience function for searches that return only one
        matching file and only one line within it so you don't have to do a
        zillion dereferences in your test.

        """
        self.found_lines_eq(query, [(content, line)])

    def found_lines_eq(self, query, expected_lines):
        """Assert that a query returns a single file and that the highlighted
        lines are as expected, modulo leading and trailing whitespace."""
        results = self.search_results(query)
        num_results = len(results)
        eq_(num_results, 1, msg='Query passed to found_lines_eq() returned '
                                 '%s files, not one.' % num_results)
        lines = results[0]['lines']
        eq_([(line['line'].strip(), line['line_number']) for line in lines],
            expected_lines)

    def found_nothing(self, query):
        """Assert that a query returns no hits."""
        results = self.search_results(query)
        eq_(results, [])

    def search_response(self, query):
        """Return the raw response of a JSON search query."""
        return self.client().get(
            self.url_for('.search',
                         tree='code',
                         q=query,
                         redirect='false'),
            headers={'Accept': 'application/json'})

    def redirect_result_eq(self, query, path, line_number, kind):
        """Assert that a redirect result of the given kind ('direct' for a
        direct result, 'single' for a single search result) is returned and
        takes the user to the given path at the given line number.

        If line_number is None, assert we point to no particular line number.

        """
        response = self.client().get(
            self.url_for('.search',
                         tree='code',
                         q=query,
                         redirect='true'),
            headers={'Accept': 'application/json'})
        eq_(response.status_code, 200)
        try:
            location = json.loads(response.data)['redirect']
        except KeyError:
            self.fail("The query didn't return a redirect result.")
        eq_(location[:location.index('?')], '/code/source/' + path)

        if kind == 'direct':
            ok_('redirect_type=direct' in location)
        elif kind == 'single':
            ok_('redirect_type=single' in location)
        else:
            self.fail("Bad 'kind' value: %s" % kind)

        if line_number is None:
            # When line_number is None, assert we point to a file in general,
            # not to a particular line number:
            ok_('#' not in location)
        else:
            # Location is something like
            # /code/source/main.cpp?from=main.cpp:6#6.
            eq_(int(location[location.index('#') + 1:]), line_number)

    def is_not_redirect_result(self, query):
        """Assert that running a query results in a normal set of results,
        possibly empty, as opposed to a result that redirects."""
        response = self.client().get(
            self.url_for('.search',
                         tree='code',
                         q=query,
                         redirect='true'),
            headers={'Accept': 'application/json'})
        eq_(response.status_code, 200)
        ok_('redirect' not in json.loads(response.data))

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
        response = self.search_response(query)
        return json.loads(response.data)['results']

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
    """Test case which builds an actual DXR config that lives on the
    filesystem

    This is suitable for complex tests with many files where the FS is the
    most convenient place to express them.

    """
    @classmethod
    def generate(cls):
        cls._config_dir_path = cls.this_dir()

    @classmethod
    def degenerate(cls):
        """Don't delete anything."""

    @classmethod
    def index(cls):
        cls.dxr_index()

    @classmethod
    def teardown_class(cls):
        with cd(cls._config_dir_path):
            run('dxr clean')
        super(DxrInstanceTestCase, cls).teardown_class()

    @classmethod
    def config_input(cls, config_dir_path):
        return file_text(join(cls._config_dir_path, 'dxr.config'))


class GenerativeTestCase(TestCase):
    """Container for tests whose source-code folders are generated rather than
    living permanently in DXR's source tree.

    You get one tree's source-code folder for free, and you can make more
    yourself if you like.

    """
    # Set this to True in a subclass to keep the generated instance around and
    # host it on port 8000 so you can examine it:
    stop_for_interaction = False

    @classmethod
    def generate(cls):
        """Make a "code" folder in the temp dir, and call ``generate_source()``
        on my subclass."""
        super(GenerativeTestCase, cls).generate()
        code_path = cls.code_dir()
        mkdir(code_path)
        cls.generate_source()

    @classmethod
    def degenerate(cls):
        """Don't delete anything."""

    @classmethod
    def index(cls):
        for tree in cls.config().trees.itervalues():
            index_and_deploy_tree(tree)

    @classmethod
    def teardown_class(cls):
        if cls.stop_for_interaction:
            print "Pausing for interaction at 0.0.0.0:8000..."
            make_app(cls.config()).run(host='0.0.0.0', port=8000)
            print "Cleaning up indices..."
        super(GenerativeTestCase, cls).teardown_class()

    @classmethod
    def generate_source(cls):
        """Generate any source code a subclass wishes."""


# TODO: Make into a GenerativeTestCase
class DxrInstanceTestCaseMakeFirst(DxrInstanceTestCase):
    """Test case which runs ``make`` before ``dxr index`` and ``make clean``
    before ``dxr clean`` within a code directory and otherwise delegates to
    DxrInstanceTestCase.

    This test is suitable for cases where some setup must be performed before
    ``dxr index`` can be run (for example extracting sources from archive).

    """
    @classmethod
    def generate(cls):
        check_call(['make'], cwd=join(cls.this_dir(), 'code'))
        super(DxrInstanceTestCaseMakeFirst, cls).generate()

    @classmethod
    def teardown_class(cls):
        check_call(['make', 'clean'], cwd=join(cls.this_dir(), 'code'))
        super(DxrInstanceTestCaseMakeFirst, cls).teardown_class()


class SingleFileTestCase(GenerativeTestCase):
    """Container for tests that need only a single source file

    You can express the source as a string rather than creating a whole bunch
    of files in the FS. I'll slam it down into a temporary DXR instance and
    then kick off the usual build process, deleting the instance afterward.

    :cvar source_filename: The filename used for the source file

    """
    source_filename = 'main'

    @classmethod
    def generate_source(cls):
        """Create a single file of source code on the FS."""
        make_file(cls.code_dir(), cls.source_filename, cls.source)

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

    def found_line_eq(self, query, content, line=None):
        """A specialization of ``found_line_eq`` that computes the line number
        if not given

        :arg line: The expected line number. If omitted, we'll compute it,
            given a match for ``content`` (minus ``<b>`` tags) in
            ``self.source``.

        """
        if not line:
            line = self._guess_line(content)
        super(SingleFileTestCase, self).found_line_eq(
                query, content, line)

    def found_lines_eq(self, query, expected_lines):
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
        super(SingleFileTestCase, self).found_lines_eq(query, expected_pairs)

    def direct_result_eq(self, query, line_number):
        return self.redirect_result_eq(
            query,
            self.source_filename,
            line_number,
            'direct')

    def single_result_eq(self, query, line_number):
        return self.redirect_result_eq(
            query,
            self.source_filename,
            line_number,
            'single')


def make_file(path, filename, contents):
    """Make file ``filename`` within ``path``, full of unicode ``contents``."""
    with open(join(path, filename), 'w') as file:
        file.write(contents.encode('utf-8'))


def _decoded_menu_on(haystack, text, text_instance=1):
    """Return the JSON-decoded menu found around the ``text_instance``th source
    code occurrence of ``text`` in the HTML ``haystack``.

    Raise an AssertionError if there is no menu there.

    """
    # We just use cheap-and-cheesy regexes for now, to avoid pulling in and
    # compiling the entirety of lxml to run pyquery.
    matches = re.finditer(
              '<a data-menu="([^"]+)"[^>]*>' + re.escape(cgi.escape(text)) + '</a>',
              haystack)
    for _ in xrange(text_instance):
        try:
            match = matches.next()
        except StopIteration:
            match = None
            break

    if match:
        return json.loads(match.group(1).replace('&quot;', '"')
                                        .replace('&lt;', '<')
                                        .replace('&gt;', '>')
                                        .replace('&amp;', '&'))
    else:
        ok_(False, "No menu around occurrence %d of '%s' was found." %
                   (text_instance, text))


def menu_on(haystack, text, *menu_items, **kwargs):
    """Assert that there is a context menu on certain text that contains
    certain menu items.

    :arg haystack: The HTML source of a page to search
    :arg text: The text contained by the menu's anchor tag. The
        ``text_instance``th menu-having anchor tag containing the text is the
        one compared against.
    :arg menu_items: Dicts whose pairs must be contained in some item of the
        menu. If an item is found to match, it is discarded can cannot be
        reused to match another element of ``menu_items``.
    :arg text_instance: An optional keyword-only arg that specifies which
        occurrence of ``text`` to compare against.  Defaults to 1 (the first
        occurrence).

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

    text_instance = kwargs.pop('text_instance', 1)
    if kwargs:
        raise TypeError('Unexpected **kwargs: %r' % kwargs)

    found_items = _decoded_menu_on(haystack, text, text_instance)
    for expected in menu_items:
        removed = removed_match(expected, found_items)
        if not removed:
            ok_(False, "No menu item with the keys %r " % (expected) +
                "was found in the menu around occurrence " +
                "%d of '%s'." % (text_instance, text))


def menu_item_not_on(haystack, text, menu_item_html, text_instance=1):
    """Assert that there is a context menu on certain text that doesn't
    contain a given menu item.

    :arg haystack: The HTML source of a page to search
    :arg text: The text contained by the menu's anchor tag. The
        ``text_instance``th menu-having anchor tag containing the text is the
        one compared against.
    :arg menu_item_html: The title of a menu item that should be missing from
        the menu, given in HTML
    :arg text_instance: Specifies which occurrence of ``text`` to compare
        against.  Defaults to 1 (the first occurrence).

    """
    found_items = _decoded_menu_on(haystack, text, text_instance)
    ok_(all(menu_item_html != item['html'] for item in found_items),
        '"%s" was found in the menu around occurrence %d of "%s".' %
         (menu_item_html, text_instance, text))
