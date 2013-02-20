"""Tests for string searches"""

from nose.tools import eq_

from dxr.testing import SingleFileTestCase, MINIMAL_MAIN


class StringTests(SingleFileTestCase):
    source = """
        void main_idea() {
        }
        """ + MINIMAL_MAIN

    def test_negated_phrase(self):
        """Make sure a negated phrase search doesn't crash."""
        eq_(self.search_results('void -"int"'), [])
