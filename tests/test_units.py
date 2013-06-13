"""Unit tests that don't fit anywhere else"""

from unittest import TestCase

from nose.tools import eq_

from dxr.build import linked_pathname


class LinkedPathnameTests(TestCase):
    def test_deep_path(self):
        """Make sure paths more than one level deep are linked correctly."""
        eq_(linked_pathname('hey/thankyou', 'code'),
            [('/code/source', 'code'),
             ('/code/source/hey', 'hey'),
             ('/code/source/hey/thankyou', 'thankyou')])

    def test_root_folder(self):
        """Make sure the root folder is treated correctly."""
        eq_(linked_pathname('', 'stuff'), [('/stuff/source', 'stuff')])
