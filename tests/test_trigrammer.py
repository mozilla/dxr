# -*- coding: utf-8 -*-
"""Tests for the regex trigram extractor"""

from unittest import TestCase

from nose.tools import eq_, assert_raises
from parsimonious.exceptions import ParseError

from dxr.trigrammer import trigrams, regex_grammar, TrigramTreeVisitor, And, Or


def test_trigrams():
    eq_(list(trigrams('')), [])
    eq_(list(trigrams('a')), [])
    eq_(list(trigrams('ab')), [])
    eq_(list(trigrams('abc')), ['abc'])
    eq_(list(trigrams('abcde')), ['abc', 'bcd', 'cde'])


#def test_something():
#    eq_(trigrams_from_regex('abc'), ['abc'])

# Make sure we don't have have both "ab" and "abc" both as possible prefixes. This is equivalent to just "ab".
# Make sure we do the right thing when the (?i) flag is set: either generate enough trigrams to cover the case insensitivity, or use a case-folder ES index. I guess we'll use a folded trigram index, like we do now. Be sure to have the query analyzer do the ucasing, because Python is not going to get that right for Unicode.
# Make sure we preserve Unicode chars.
# Be sure to escape - if it's the last char in a character class before passing it to ES.

# prefixes: abc | cba
# suffixes: def
# exact: abcdef | cbadef
#
# prefixes: ab abcd abef
#              abcd abef
# suffixes: ef cdef abef
#              cdef abef
# exact: Ø


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
