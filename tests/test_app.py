"""Tests for the dxr.app module

Much of the module is covered in the course of the integration tests that test
everything else. Here are a few unit tests.

"""
from unittest import TestCase

from nose.tools import eq_

from dxr.app import _linked_pathname


class LinkedPathnameTests(TestCase):
    def test_deep_path(self):
        """Make sure paths more than one level deep are linked correctly."""
        eq_(_linked_pathname('hey/thankyou', 'code'),
            [('/code/source', 'code'),
             ('/code/source/hey', 'hey'),
             ('/code/source/hey/thankyou', 'thankyou')])

    def test_root_folder(self):
        """Make sure the root folder is treated correctly."""
        eq_(_linked_pathname('', 'stuff'), [('/stuff/source', 'stuff')])
