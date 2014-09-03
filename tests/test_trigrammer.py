# -*- coding: utf-8 -*-
"""Tests for the regex trigram extractor"""

from unittest import TestCase

from nose import SkipTest
from nose.tools import eq_, ok_, assert_raises
from parsimonious.exceptions import ParseError

from dxr.trigrammer import regex_grammar, TrigramTreeVisitor, And, Or, _coalesce_strings


# Make sure we don't have have both "ab" and "abc" both as possible prefixes. This is equivalent to just "ab".
# Make sure we do the right thing when the (?i) flag is set: use a case-folder ES index.
# Make sure we preserve Unicode chars.
# Be sure to escape "-" if it's the last char in a character class before passing it to ES. [No longer applies, since we use JS regexes.]

# prefixes: abc | cba
# suffixes: def
# exact: abcdef | cbadef
#
# prefixes: ab abcd abef
#              abcd abef
# suffixes: ef cdef abef
#              cdef abef
# exact: Ø


def test_coalesce_strings():
    eq_(list(_coalesce_strings(['a', 'b', 'c'])), ['abc'])
    eq_(list(_coalesce_strings(['a', 'b', Or(['c', 'd']), 'e'])),
        ['ab', Or(['c', 'd']), 'e'])


class SimplificationTests(TestCase):
    """Tests for tree simplification, especially that which results in static
    strings we might use in, for example, the PathFilter."""

    def test_single_strings(self):
        """These should simplify down to single strings."""
        eq_(And(['smoo']).simplified(), 'smoo')
        eq_(And(Or(['smoo'])).simplified(), 'smoo')
        eq_(Or(And(['smoo'])).simplified(), 'smoo')

    def test_nopes(self):
        """These examples should not simplify down to strings."""
        ok_(not isinstance(And(['smoo', Or(['hi'])]).simplified(), basestring))
        eq_(Or(['smoo', 'hi']).simplified(), Or(['smoo', 'hi']))

    def test_simple_strings(self):
        """An And or Or with one child should turn into that child."""
        eq_(visit_regex('abcd').simplified(), 'abcd')

    def test_string_coalescing(self):
        """We should be smart enough to merge these into a single string."""
        raise SkipTest("We will need more metadata on the tree nodes (the 'exact' datum from the Cox method) to tell when it's safe to coalesce a, b, and c in the parent node after they were simplified out of lower-level children.")
        eq_(visit_regex('(a)(b)(c)').simplified(), 'abc')

    def test_not_coalescing_over_uselesses(self):
        """Don't coalesce 2 strings that have a USELESS between them."""
        eq_(visit_regex('ab*c').simplified(), And(['a', 'c']))

    def test_big_tree(self):
        """Try the ambitious tree (a|b)(c|d)."""
        eq_(Or([And([Or([And(['a']), And(['b'])]),
                     Or([And(['c']), And(['d'])])])]).simplified(),
            And([Or(['a', 'b']),
                 Or(['c', 'd'])]))

    def test_empty(self):
        """Pin down what empty top-level trees turn into.

        I'm not sure the current state is desirable. '' is another
        possibility, but I worry about what Or(['hi', '']) means.

        """
        eq_(Or([And()]).simplified(), Or())


def visit_regex(regex):
    return TrigramTreeVisitor().visit(regex_grammar.parse(regex))


class StringExtractionTests(TestCase):
    """Tests for our ability to extract static strings from regexes

    This covers the TrigramTreeVisitor and the StringTreeNodes.

    """
    def test_merge_literals(self):
        """Make sure we know how to merge adjacent char literals."""
        eq_(visit_regex('abcd'), Or([And(['abcd'])]))

    def test_2_branches(self):
        eq_(visit_regex('ab|cd'), Or([And(['ab']), And(['cd'])]))

    def test_3_branches(self):
        eq_(visit_regex('ab|cd|ef'),
            Or([And(['ab']), And(['cd']), And(['ef'])]))

    def test_anded_uselesses(self):
        """Make USELESSes break up contiguous strings of literals."""
        eq_(visit_regex('ab[^q]cd'),
            Or([And(['ab', 'cd'])]))

    def test_empty_branch(self):
        """Make sure the right kind of tree is built when a branch is empty."""
        eq_(visit_regex('(a||b)'),
            Or([And([Or([And(['a']), And(['']), And(['b'])])])]))

    def test_nested_tree(self):
        """Make sure Ors containing Ands build properly."""
        eq_(visit_regex('ab[^q](cd|ef)'),
            Or([And(['ab', Or([And(['cd']), And(['ef'])])])]))
        eq_(visit_regex('ab(cd|ef)'),
            Or([And(['ab', Or([And(['cd']), And(['ef'])])])]))

    def test_and_containing_ors(self):
        """Does this explode? Right now, visit_branch assumes that Ands receive only strings or USELESS."""
        eq_(visit_regex('(a|b)(c|d)'),
            Or([And([Or([And(['a']), And(['b'])]), Or([And(['c']), And(['d'])])])]))

    def test_wtf(self):
        """Guard against an ill-defined WTF we had."""
        eq_(visit_regex('(aa|b)(c|d)'),
            Or([And([Or([And(['aa']), And(['b'])]), Or([And(['c']), And(['d'])])])]))


def test_parse_classes():
    """Make sure we recognize character classes."""

    class_rule = regex_grammar['class']

    def parse_class(pattern):
        class_rule.parse(pattern)

    def dont_parse_class(pattern):
        assert_raises(ParseError,
                      class_rule.parse,
                      pattern)

    def assert_matches(pattern, text):
        eq_(class_rule.match(pattern).text, text)

    # These should match all the way to the end:
    for pattern in ['[]]', '[^]]', r'[\d-]', r'[a\]]', r'[()[\]{}]', '[]()[{}]', '[a-zA-Z0-9]', '[abcde]']:
        yield parse_class, pattern

    # These shouldn't match:
    for pattern in ['[]', '[^]', '[']:
        yield dont_parse_class, pattern

    # Make sure we don't go too far:
    for pattern, text in [('[abc]]', '[abc]'),
                          ('[[0-9]qux', '[[0-9]'),
                          (r'[^\a\f\]]abc', r'[^\a\f\]]')]:
        yield assert_matches, pattern, text


def test_parse_regexp():
    regex_grammar.parse('hello+ dolly')
    regex_grammar.parse('hello+|hi')
    regex_grammar.parse(r'(hello|hi) dolly')
    regex_grammar.parse(r'(hello|hi|) dolly')
    regex_grammar.parse(r'(hello||hi) dolly')
    regex_grammar.parse(r'|hello|hi')
    regex_grammar.parse(ur'aböut \d{2}')
