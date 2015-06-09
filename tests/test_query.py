"""Tests for the dxr.build module

Much of the module is covered in the course of the integration tests that test
everything else. Here are a few unit tests.

"""
from unittest import TestCase

from nose.tools import eq_

from dxr.query import fix_extents_overlap


class FixExtentsOverlapTests(TestCase):
    """Tests for fix_extents_overlap()"""

    def test_duplicate(self):
        """Duplicate extents should be combined."""
        eq_(list(fix_extents_overlap([(22, 34), (22, 34)])),
            [(22, 34)])

    def test_disjoint(self):
        """Disjoint extents should remain unmolested."""
        eq_(list(fix_extents_overlap([(1, 7), (8, 12)])),
            [(1, 7), (8, 12)])

    def test_overlap(self):
        """Overlapping extents should be merged."""
        eq_(list(fix_extents_overlap([(1, 7), (5, 8)])),
            [(1, 8)])

    def test_adjacent(self):
        """Adjacent extents should be coalesced.

        This is not important, but it's nice.

        """
        eq_(list(fix_extents_overlap([(1, 7), (7, 10)])),
            [(1, 10)])

    def test_short(self):
        """Short inputs should work."""
        eq_(list(fix_extents_overlap([])),
            [])
        eq_(list(fix_extents_overlap([(1, 2)])),
            [(1, 2)])

    def test_zero(self):
        """Work even if the highlighting starts at offset 0."""
        eq_(list(fix_extents_overlap([(0, 3), (2, 5), (11, 14)])),
            [(0, 5), (11, 14)])
