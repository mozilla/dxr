"""Tests for the machinery that takes offsets and markup bits from plugins and
decorates source code with them to create HTML"""

from unittest import TestCase
import warnings
from warnings import catch_warnings

from more_itertools import first
from nose.tools import eq_

from dxr.utils import cumulative_sum
from dxr.lines import (line_boundaries, remove_overlapping_refs, Region, LINE,
                       Ref, balanced_tags, finished_tags, tag_boundaries,
                       html_line, nesting_order, balanced_tags_with_empties,
                       es_lines, tags_per_line)


def test_line_boundaries():
    """Make sure we find the correct line boundaries with all sorts of line
    endings, even in files that don't end with a newline."""
    eq_(list((point, is_start) for point, is_start, _ in
             line_boundaries('abc\ndef\r\nghi\rjkl'.splitlines(True))),
        [(4, False),
         (9, False),
         (13, False),
         (16, False)])


class RemoveOverlappingTests(TestCase):
    def test_misbalanced(self):
        """Make sure we cleanly excise a tag pair from a pair of interleaved
        tags."""
        # A  _________          (2, 6)
        # B        ____________ (5, 9)
        a = Ref('a')
        b = Ref('b')
        tags = [(2, True, a),
                (5, True, b),
                (6, False, a),
                (9, False, b)]
        with catch_warnings():
            warnings.simplefilter('ignore')
            remove_overlapping_refs(tags)
        eq_(tags, [(2, True, a), (6, False, a)])

    def test_overlapping_regions(self):
        """Regions (as opposed to refs) are allowed to overlap and shouldn't be
        disturbed::

            A           _________          (2, 6)
            B (region)        ____________ (5, 9)

        """
        a = Ref('a')
        b = Region('b')
        tags = [(2, True, a),
                (5, True, b),
                (6, False, a),
                (9, False, b)]
        original_tags = tags[:]
        remove_overlapping_refs(tags)
        eq_(tags, original_tags)


def spaced_tags(tags):
    """Render (point, is_start, payload) triples as human-readable
    representations."""
    segments = []
    for point, is_start, payload in tags:
        segments.append(' ' * point + ('<%s%s>' % ('' if is_start else '/',
                                                   'L' if payload is LINE else
                                                        payload.payload)))
    return '\n'.join(segments)


def tags_from_text(text):
    """Return unsorted tags based on an ASCII art representation."""
    for line in text.splitlines():
        start = line.find('_')
        label, prespace, underscores = line[0], line[2:start], line[start:]
        ref = Region(label)
        yield len(prespace), True, ref
        yield len(prespace) + len(underscores) - 1, False, ref


def test_tags_from_text():
    # str() so the Region objs compare equal
    eq_(str(list(tags_from_text('a ______________\n'
                                'b ______\n'
                                'c     _____'))),
        '[(0, True, Region("a")), (13, False, Region("a")), '
        '(0, True, Region("b")), (5, False, Region("b")), '
        '(4, True, Region("c")), (8, False, Region("c"))]')


class BalancedTagTests(TestCase):
    def test_horrors(self):
        """Try a fairly horrific scenario::

            A _______________            (0, 7)
            B     _________              (2, 6)
            C           ____________     (5, 9)
            D                    _______ (8, 11)
            E                         __ (10, 11)
              0   2     5 6 7    8 9

        A contains B. B closes while C's still going on. D and E end at the
        same time. There's even a Region in there.

        """
        a, b, c, d, e = Ref('a'), Region('b'), Ref('c'), Ref('d'), Ref('e')
        tags = [(0, True, a), (2, True, b), (5, True, c), (6, False, b),
                (7, False, a), (8, True, d), (9, False, c), (10, True, e),
                (11, False, e), (11, False, d)]

        eq_(spaced_tags(balanced_tags(tags)),
            '<L>\n'
            '<a>\n'
            '  <b>\n'
            '     <c>\n'
            '      </c>\n'
            '      </b>\n'
            '      <c>\n'
            '       </c>\n'
            '       </a>\n'
            '       <c>\n'
            '        <d>\n'
            '         </d>\n'
            '         </c>\n'
            '         <d>\n'
            '          <e>\n'
            '           </e>\n'
            '           </d>\n'
            '           </L>')

    def test_coincident(self):
        """We shouldn't emit pointless empty tags when tempted to."""
        tags = sorted(tags_from_text('a _____\n'
                                     'b _____\n'
                                     'c _____\n'), key=nesting_order)
        eq_(spaced_tags(balanced_tags(tags)),
            '<L>\n'
            '<a>\n'
            '<b>\n'
            '<c>\n'
            '    </c>\n'
            '    </b>\n'
            '    </a>\n'
            '    </L>')

    def test_coincident_ends(self):
        """We shouldn't emit empty tags even when coincidently-ending tags
        don't start together."""
        # These Regions aren't in startpoint order. That makes tags_from_test()
        # instantiate them in a funny order, which makes them sort in the wrong
        # order, which is realistic.
        tags = sorted(tags_from_text('d      _______\n'
                                     'c    _________\n'
                                     'b  ___________\n'
                                     'a ____________\n'
                                     'e     ___________\n'), key=nesting_order)
        eq_(spaced_tags(balanced_tags(tags)),
            '<L>\n'
            '<a>\n'
            ' <b>\n'
            '   <c>\n'
            '    <e>\n'
            '     <d>\n'
            '           </d>\n'
            '           </e>\n'
            '           </c>\n'
            '           </b>\n'
            '           </a>\n'
            '           <e>\n'
            '              </e>\n'
            '              </L>')

    def test_multiline_comment(self):
        """Multi-line spans should close at the end of one line and reopen at
        the beginning of the next."""
        c = Region('c')
        c2 = Region('c')
        l = LINE
        tags = [(0, True, c),
                (79, False, c),
                (80, False, l),

                (80, True, c2),
                (151, False, l),

                (222, False, l),

                (284, False, c2),
                (285, False, l),

                (286, False, l)]
        text = u"""/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */
/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"""
        lines = text.splitlines(True)
        offsets = cumulative_sum(map(len, lines))
        actual_lines = [html_line(text_line.rstrip('\r\n'), e, offset) for
                        text_line, e, offset in
                        zip(lines, tags_per_line(balanced_tags(tags)), offsets)]
        expected_lines = ['<span class="c">/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */</span>',
                          '<span class="c">/* This Source Code Form is subject to the terms of the Mozilla Public</span>',
                          '<span class="c"> * License, v. 2.0. If a copy of the MPL was not distributed with this</span>',
                          '<span class="c"> * file, You can obtain one at http://mozilla.org/MPL/2.0/. */</span>',
                          '']
        eq_(actual_lines, expected_lines)

    def test_empty(self):
        """Some files are empty. Make sure they work."""
        eq_(list(balanced_tags([])), [])


def test_tag_boundaries():
    """Sanity-check ``tag_boundaries()``."""
    eq_(str(list(tag_boundaries([], [(0, 3, 'a'), (3, 5, 'b')]))),
        '[(0, True, Region("a")), (3, False, Region("a")), '
        '(3, True, Region("b")), (5, False, Region("b"))]')


def test_simple_html_line():
    """See if the offsets are right in simple HTML stitching."""
    a = Region('a')
    b = Region('b')
    line = LINE
    text = 'hello'
    eq_(html_line(text, first(tags_per_line([(0, True, line),
                                             (0, True, a), (3, False, a),
                                             (3, True, b), (5, False, b),
                                             (5, False, line)])), 0),
        '<span class="a">hel</span><span class="b">lo</span>')


def text_to_html_lines(text, refs=(), regions=()):
    """Run the full pipeline, and return a list of htmlified lines of ``text``
    with markup interspersed for ``regions``."""
    lines = text.splitlines(True)
    offsets = cumulative_sum(map(len, lines))
    return [html_line(text_line, e, o) for (text_line, e, o) in
            zip(lines, tags_per_line(finished_tags(lines,
                                                   refs,
                                                   regions)), offsets)]


class IntegrationTests(TestCase):
    """Tests for several layers at once, though not necessarily all of them"""

    def test_simple(self):
        """Sanity-check the combination of finished_tags, es_lines and
        html_line, which constitutes an end-to-end run of the pipeline."""
        eq_(text_to_html_lines('hello', regions=[(0, 3, 'a'), (3, 5, 'b')]),
            [u'<span class="a">hel</span><span class="b">lo</span>'])

    def test_split_anchor_avoidance(self):
        """Don't split anchor tags when we can avoid it."""
        eq_(text_to_html_lines('this that', [(0, 9, ({}, ''))], [(0, 4, 'k')]),
            [u'<a data-menu="{}"><span class="k">this</span> that</a>'])

    def test_split_anchor_across_lines(self):
        """Support unavoidable splits of an anchor across lines."""
        eq_(text_to_html_lines('this\nthat', refs=[(0, 9, ({}, ''))]),
            [u'<a data-menu="{}">this</a>', u'<a data-menu="{}">that</a>'])

    def test_horrors(self):
        """Untangle a circus of interleaved tags, tags that start where others
        end, and other untold wretchedness."""
        # This is a little brittle. All we really want to test is that each
        # span of text is within the right spans. We don't care what order the
        # span tags are in.
        eq_(text_to_html_lines('this&that',
                               regions=[(0, 9, 'a'), (1, 8, 'b'),
                                        (4, 7, 'c'), (3, 4, 'd'),
                                        (3, 5, 'e'), (0, 4, 'm'),
                                        (5, 9, 'n')]),
            [u'<span class="a"><span class="m">t<span class="b">hi<span class="d"><span class="e">s</span></span></span></span><span class="b"><span class="e"><span class="c">&amp;</span></span><span class="c"><span class="n">th</span></span><span class="n">a</span></span><span class="n">t</span></span>'])

    def test_empty_tag_boundaries(self):
        """Zero-length tags should be filtered out by ``tag_boundaries()``.

        If they are not, the start of a tag can sort after the end, crashing
        the tag balancer.

        """
        text_to_html_lines('hello!',
                           regions=[(3, 3, 'a'), (3, 5, 'b')])
