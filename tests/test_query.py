# -*- coding: utf-8 -*-
"""Tests for the query parser and executor"""

from unittest import TestCase

from nose.tools import eq_

from dxr.query import query_grammar, QueryVisitor


class ParserTests(TestCase):
    def test_smoke(self):
        """Initial smoke tests for the query grammar"""
        query_grammar.parse("re:(?i)snork")
        query_grammar.parse("re:smoo bar baz")
        query_grammar.parse("-baz -foo")
        query_grammar.parse("-baz +qual +type: +type:good +-type:hey")
        query_grammar.parse("- -+ +- re: smoo")
        #query_grammar.parse(u'börg')


def test_quotes():
    """Test the quoted-string regexes, both with double and single quotes."""
    tests = [(r'"hi there"', r'hi there'),
             (r'"hi"there"', r'hi"there'),
             (r'"hi"there"d', r'hi"there"d'),  # Don't prematurely stop capturing when we hit a quote without a space after it.
             (r'"hi\" and"', r'hi" and'),  # Don't count a backslashed quote as a closing one, even if it has a space after it.
             (r'"hi \pthere\"boogy"', r'hi \pthere"boogy'),  # Preserve backslashes that don't escape a quote.
             (r'"multi word', r'multi word')]  # Get all words in a space-having input without closing quotes.
    for rule_name, transform in [('double_quoted_text',
                                  lambda x: x),
                                 ('single_quoted_text',
                                  lambda x: x.replace('"', "'"))]:
        rule = query_grammar[rule_name]
        for input, output in tests:
            def test_something():
                eq_(QueryVisitor().visit(rule.match(transform(input))),
                    transform(output))
            yield test_something
