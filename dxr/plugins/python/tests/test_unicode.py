# -*- coding: utf-8 -*-
"""Tests that try to provoke UnicodeErrors"""

from dxr.plugins.python.tests import PythonSingleFileTestCase


class UnicodeTests(PythonSingleFileTestCase):
    source = u'resp = "あいうえお"'

    def test_null(self):
        """An empty test to get the build to run

        If it doesn't crash, the test passed.

        """
