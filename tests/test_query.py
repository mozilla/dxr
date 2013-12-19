"""Tests for the query parser and executor"""

from unittest import TestCase

from nose.tools import eq_

from dxr.query import query_grammar


class ParserTests(TestCase):
    def test_smoke(self):
        """Initial smoke tests for the query grammar"""
        print query_grammar.parse("re:(?i)snork")
        print query_grammar.parse("re:smoo bar baz")
        print query_grammar.parse("-baz -foo")        
        print query_grammar.parse("-baz +qual +type: +type:good +-type:hey")
