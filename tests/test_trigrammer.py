# -*- coding: utf-8 -*-
"""Tests for the regex trigram extractor"""

from unittest import TestCase

from nose import SkipTest
from nose.tools import eq_, ok_, assert_raises
from parsimonious import ParseError
from parsimonious.expressions import OneOf

from dxr.trigrammer import (regex_grammar, SubstringTreeVisitor, And, Or,
                            BadRegex, JsRegexVisitor, PythonRegexVisitor)


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
        ok_(not isinstance(And(['smoo', Or(['him'])]).simplified(), basestring))
        eq_(Or(['smoo', 'him']).simplified(), Or(['smoo', 'him']))

    def test_simple_strings(self):
        """An And or Or with one child should turn into that child."""
        eq_(visit_regex('abcd').simplified(), 'abcd')

    def test_string_coalescing(self):
        """We should be smart enough to merge these into a single string."""
        raise SkipTest("We will need more metadata on the tree nodes (the 'exact' datum from the Cox method) to tell when it's safe to coalesce a, b, and c in the parent node after they were simplified out of lower-level children.")
        eq_(visit_regex('(a)(b)(c)').simplified(), 'abc')

    def test_not_coalescing_over_uselesses(self):
        """Don't coalesce 2 strings that have a USELESS between them."""
        eq_(visit_regex('arkb*cork').simplified(), And(['ark', 'cork']))

    def test_big_tree(self):
        """Try the ambitious tree (a|b)(c|d)."""
        eq_(Or([And([Or([And(['alpha']), And(['bravo'])]),
                     Or([And(['charlie']), And(['delta'])])])]).simplified(),
            And([Or(['alpha', 'bravo']),
                 Or(['charlie', 'delta'])]))

    def test_empty(self):
        """Pin down what empty top-level trees turn into.

        I'm not sure the current state is desirable. '' is another
        possibility, but I worry about what Or(['hi', '']) means. [It means
        "hi can occur, or not", which makes it useless.]

        """
        eq_(Or([And()]).simplified(), '')

    def test_short_ngram_removal(self):
        """Substrings shorter than 3 chars should be removed."""
        eq_(And(['oof', 'by', 'smurf']).simplified(), And(['oof', 'smurf']))
        eq_(Or(['', 'by', 'smurf']).simplified(), 'smurf')
        eq_(Or([And(['', 'e', 'do']), 'hi']).simplified(), '')


def visit_regex(regex):
    return SubstringTreeVisitor().visit(regex_grammar.parse(regex))


def eq_simplified(regex, expected):
    """Visit a regex, simplify it, and return whether it's equal to an
    expected value.

    Doesn't strip away shorter-than-trigram strings. That's tested for in
    SimplificationTests.

    """
    eq_(visit_regex(regex).simplified(min_length=1), expected)


class StringExtractionTests(TestCase):
    """Tests for our ability to extract static strings from regexes

    This covers the SubstringTreeVisitor and the SubstringTree.

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

    def test_wildcards(self):
        """Wildcards should be stripped off as useless."""
        eq_simplified('.*abc.*', 'abc')



class ClassTests(TestCase):
    """Tests for extracting (Ors of) strings from backet expressions."""

    def test_classes(self):
        """Exercise the enumerated case."""
        eq_simplified('[abc]', Or(['a', 'b', 'c']))

    def test_range(self):
        """Make sure character ranges expand."""
        eq_simplified('[a-c]', Or(['a', 'b', 'c']))

    def test_big_range(self):
        """Make sure huge character ranges get given up on, rather than
        building humongous Ors."""
        eq_simplified('[a-z]', '')

    def test_trailing_hyphen(self):
        """Trailing hyphens should be considered just ordinary hyphens."""
        eq_simplified('[a-]', Or(['a', '-']))

    def test_leading_bracket(self):
        """A ] as the first char in a class should be considered ordinary."""
        eq_simplified('[]a]', Or([']', 'a']))
        eq_simplified('[]]', ']')

    def test_ordinary_specials(self):
        """Chars that are typically special should be ordinary within char
        classes."""
        eq_simplified('[$]', '$')

    def test_inverted(self):
        """We give up on inverted classes for now."""
        eq_simplified('[^a-c]', '')

    def test_multi_char_specials(self):
        """We give up on backslash specials which expand to multiple chars,
        for now."""
        eq_simplified(r'[\s]', '')

    def test_out_of_order_range(self):
        """Out-of-order ranges shouldn't even appear to parse."""
        assert_raises(BadRegex, visit_regex, '[c-a]')

    def test_unicode(self):
        """Make sure unicode range bounds work."""
        # This is a span of only a few code points: shouldn't be USELESS.
        eq_simplified(u'[♣-♥]', Or([u'♣', u'♤', u'♥']))


def test_parse_classes():
    """Make sure we recognize character classes."""

    class_or_inverted = OneOf(regex_grammar['inverted_class'],
                              regex_grammar['class'],
                              name='class_or_inverted')

    def parse_class(pattern):
        class_or_inverted.parse(pattern)

    def dont_parse_class(pattern):
        assert_raises(ParseError,
                      class_or_inverted.parse,
                      pattern)

    def assert_matches(pattern, text):
        eq_(class_or_inverted.match(pattern).text, text)

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
    assert_raises(ParseError, regex_grammar.parse, '[smoo')

    # This isn't supported yet, so it's better to throw an error than to
    # quietly misinterpret the user's intent:
    assert_raises(ParseError, regex_grammar.parse, '(?:hi)')


def js_eq(regex, expected):
    """Assert that taking a regex apart into an AST and then building a JS
    regex from it matches the expected result.

    :arg regex: A string representing a regex pattern
    :arg expected: What to compare the reconstructed regex against

    """
    eq_(JsRegexVisitor().visit(regex_grammar.parse(regex)), expected)


def test_js_visitor():
    """Make sure we can render out JS regexes from parse trees."""
    # Ones that are the same as the input:
    for pattern in [
            'hello',
            u'♥',
            r'(See|Hear|Feel)\s{2}Dick\s(run){3,6}!',  # backslash metas, ors, {}s
            r'\v* ?\t+',  # backslash specials, more quantifiers
            '',
            'matches$^nothing',
            '[^inver-ted-][]cla-ss]',
            r'\x41',
            r'hork\.cpp',
            r'\\cA'  # Keep literal backslashes.
            ]:
        yield js_eq, pattern, pattern

    # Ones that are different from the input:
    for pattern, new_pattern in [
            (r'\cA', 'cA'),  # \c has a special meaning in JS but not in Python.
            (r'\Q', 'Q')  # Strip backslashes from boring literals.
            ]:
        yield js_eq, pattern, new_pattern


def test_python_visitor():
    """Make sure we can render out Python regexes from parse trees.

    There's just one difference from JS so far.

    """
    eq_(PythonRegexVisitor().visit(regex_grammar.parse(r'\a')), r'\a')
