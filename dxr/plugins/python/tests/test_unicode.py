# -*- coding: utf-8 -*-
"""Tests that try to provoke UnicodeErrors"""

from textwrap import dedent

from dxr.plugins.python.tests import PythonSingleFileTestCase


class UnicodeTests(PythonSingleFileTestCase):
    source = u'resp = "あいうえお"'

    def test_null(self):
        """An empty test to get the build to run

        If it doesn't crash, the test passed.

        """


class EncodingCommentTests(PythonSingleFileTestCase):
    source = u'# -*- coding: utf-8 -*-\ndef foo():\n    return 42'

    def test_encoding_comment_files_are_not_skipped(self):
        """Calling ast.parse on unicode objects that have an encoding comment
        in the first two lines is subject to a bug in Python 2.  See
        http://bugs.python.org/issue22221.  Show that we can process
        such a file without skipping or error.

        """
        self.found_line_eq('function:foo', "def <b>foo</b>():", 2)


class UnicodeOffsetTests(PythonSingleFileTestCase):
    source = dedent(u"""
    # -*- coding: utf-8 -*-

    def kilroy():
        return "Mr. Roboto"

    def main():
        # domo arigato
        print u"どうもありがとう " + kilroy()
    """)

    def test_call_offsets(self):
        """Check that the offset of the function call is calculated in unicode
        characters, not bytes.

        """
        self.found_line_eq('callers:kilroy', u'print u"どうもありがとう " + <b>kilroy</b>()', 9)
