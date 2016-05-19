# -*- coding: utf-8 -*-
"""Tests for the query parser"""

from unittest import TestCase

from nose.tools import eq_

from dxr.plugins import plugins_named
from dxr.query import query_grammar, QueryVisitor


class VisitorTests(TestCase):
    """Make sure ``QueryVisitor`` is putting together sane data structures."""

    def visit(self, query):
        return QueryVisitor().visit(query_grammar(plugins_named(['core', 'clang'])).parse(query))

    def test_overall(self):
        """Test the overall structure."""
        eq_(self.visit('regexp:(?i)snork'),
            [{'arg': '(?i)snork',
              'name': 'regexp',
              'not': False,
              'case_sensitive': False,
              'qualified': False}])

    def test_tricksy_orphanses(self):
        """Try to trick the parser into prematurely committing to various
        classifications."""
        eq_(self.visit('- -+ @ +- -+fred +type: +-type:hey type: smoo hi:mom +boo'),
            [{'arg': '-',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False},
             {'arg': '+',
              'name': 'text',
              'not': True,
              'case_sensitive': False,
              'qualified': False},
             {'arg': '@',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False},
             {'arg': '+-',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False},
             {'arg': '+fred',
              'name': 'text',
              'not': True,
              'case_sensitive': False,
              'qualified': False},
             {'arg': '+type:',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False},
             {'arg': '+-type:hey',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False},
             {'arg': 'type:',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False},
             {'arg': 'smoo',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False},
             {'arg': 'hi:mom',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False},
             {'arg': '+boo',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False}])

    def test_normal_things(self):
        """Make sure normal, everyday things that should work do."""
        eq_(self.visit('regexp:smoo -regexp:foo|bar -baz qux foo Foo @foo type:yeah'),
            [{'arg': 'smoo',
              'name': 'regexp',
              'not': False,
              'case_sensitive': False,
              'qualified': False},
             {'arg': 'foo|bar',
              'name': 'regexp',
              'not': True,
              'case_sensitive': False,
              'qualified': False},
             {'arg': 'baz',
              'name': 'text',
              'not': True,
              'case_sensitive': False,
              'qualified': False},
             {'arg': 'qux',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False},
             {'arg': 'foo',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False},
             {'arg': 'Foo',
              'name': 'text',
              'not': False,
              'case_sensitive': True,
              'qualified': False},
             {'arg': 'foo',
              'name': 'text',
              'not': False,
              'case_sensitive': True,
              'qualified': False},
             {'arg': 'yeah',
              'name': 'type',
              'not': False,
              'case_sensitive': False,
              'qualified': False}])

    def test_qualified(self):
        """Make sure fully-qualified filters are recognized."""
        eq_(self.visit('+type:Snork'),
            [{'arg': 'Snork',
              'name': 'type',
              'not': False,
              'case_sensitive': True,
              'qualified': True}])

    def test_unclosed_quotes(self):
        """An unclosed quoted string should be considered as if it were closed.

        This makes it more likely we perform the same sorts of searches while
        you're still typing as we will once you get to the end, yielding more
        useful incremental results.

        """
        eq_(self.visit('"this here thing'),
            [{'arg': 'this here thing',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False}])

    def test_literal_quotes(self):
        """Make sure we can express literal quotes when we want to.

        Also accidentally test ignoring of leading and trailing spaces.

        """
        eq_(self.visit(""" '"this' 'here"' "'thing'" """),
            [{'arg': '"this',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False},
             {'arg': 'here"',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False},
             {'arg': "'thing'",
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False}])

    def test_bare_unicode(self):
        """Make sure non-ASCII chars are recognized in bare text."""
        eq_(self.visit(u'börg'),
            [{'arg': u'börg',
              'name': 'text',
              'not': False,
              'case_sensitive': False,
              'qualified': False}])

    def test_empty(self):
        """An empty query shouldn't give a ParseError."""
        eq_(self.visit(''), [])


# Not in VisitorTests because nose doesn't support test generators in TestCase
# subclasses.
def test_quotes():
    """Test the quoted-string regexes, both with double and single quotes."""
    tests = [(r'"hi there"', r'hi there'),
             (r'"hi"there"', r'hi"there'),
             (r'"hi"there"d', r'hi"there"d'),  # Don't prematurely stop capturing when we hit a quote without a space after it.
             (r'"hi\" and"', r'hi" and'),  # Don't count a backslashed quote as a closing one, even if it has a space after it.
             (r'"hi \pthere\"boogy"', r'hi \pthere"boogy'),  # Preserve backslashes that don't escape a quote.
             (r'"multi word', r'multi word'),  # Get all words in a space-having input without closing quotes.
             (r'"\\""', r'\"'),  # It is possible to express backslash-quote.
             (ur'"sñork"', ur'sñork')]  # Unicode holds up in quoted strings.
    for rule_name, transform in [('double_quoted_text',
                                  lambda x: x),
                                 ('single_quoted_text',
                                  lambda x: x.replace('"', "'"))]:
        rule = query_grammar([])[rule_name]
        for input, output in tests:
            def test_something():
                eq_(QueryVisitor().visit(rule.match(transform(input))),
                    transform(output))
            yield test_something
