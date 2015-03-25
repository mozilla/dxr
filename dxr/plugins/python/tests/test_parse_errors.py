import warnings
from textwrap import dedent

from nose.tools import eq_, ok_

from dxr.plugins.python.tests import PythonSingleFileTestCase


class WarningTestCase(PythonSingleFileTestCase):
    @classmethod
    def config_input(cls, config_dir_path):
        # We need to disable workers because catch_warnings does not
        # support multi-threaded or multi-process capturing.
        config = super(WarningTestCase, cls).config_input(config_dir_path)
        config['DXR']['workers'] = 0
        return config

    @classmethod
    def setup_class(cls):
        # Wrap the normal setup to catch warnings.
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter('always')
            super(WarningTestCase, cls).setup_class()
        cls.warnings = caught_warnings


class ParseErrorTestMixin(object):
    """Store common test method on a mixin so nose doesn't try to run it
    except on the TestCase subclasses.

    """
    def test_parse_error(self):
        """Make sure nothing is indexed for a file with invalid Python
        code, and that the build process raised warnings about it.

        """
        self.found_nothing('class:TestClass')

        # One warning for the pre-index analyzing, and one for indexing.
        eq_(len(self.warnings), 1)
        ok_('Failed to analyze main.py' in unicode(self.warnings[0].message))


class InvalidPythonTest(WarningTestCase, ParseErrorTestMixin):
    source = dedent("""
        from foo import bar

        biff = -8bazinvalid  # That ain't right

        class TestClass(object):
            pass
    """)


class InvalidTokenTest(WarningTestCase, ParseErrorTestMixin):
    source = dedent("""
        from foo import bar

        class TestClass(object):
            pass

        '''Tokenizer fails on un-closed strings. We test this particular
        situation so that if we ever refactor the Python plugin to tokenize
        the code before the AST parses it, we still fail properly even if the
        tokenizer fails first.
    """)
