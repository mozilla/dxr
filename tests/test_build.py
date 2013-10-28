"""Tests for the machinery that takes offsets and markup bits from plugins and
decorates source code with them to create HTML"""

from unittest import TestCase
import warnings
from warnings import catch_warnings

from nose.tools import eq_

from dxr.build import (line_boundaries, remove_overlapping_refs, Region,
                       Ref, balanced_tags)


class DecorationTests(TestCase):
    def test_line_boundaries(self):
        """Make sure we find the correct line boundaries with all sorts of line
        endings, even in files that don't end with a newline."""
        eq_(list((point, is_start) for point, is_start, _ in line_boundaries('abc\ndef\r\nghi\rjkl')),
            [(0, True), (3, False),
             (4, True), (8, False),
             (9, True), (12, False),
             (13, True), (15, False)])


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
        segments.append(' ' * point + ('<%s%s>' % ('' if is_start else '/', payload.payload)))
    return '\n'.join(segments)


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
"""<a>
  <b>
     <c>
      </c>
      </b>
      <c>
       </c>
       </a>
       <c>
        <d>
         </d>
         </c>
         <d>
          <e>
           </e>
           </d>""")

    def test_coincident(self):
        """See if we emit pointless empty tags when tempted to."""
        a, b, c = Region('a'), Region('b'), Region('c')
        tags = [(0, True, a), (0, True, b), (0, True, c),
                (4, False, a), (4, False, b), (4, False, c)]
        print spaced_tags(balanced_tags(tags))
        eq_(spaced_tags(balanced_tags(tags)),
"""<a>
<b>
<c>
    </c>
    </b>
    </a>""")

"""See what __
            __
            __ does. See if it spits out a lot of empty tag pairs. We could always write a custom sorter that flips the sort order when is_start is False and puts the obj ID of the payload into the sort mix."""

"""And ______________
 b           ___________
 c           ___________
 d           ___________
          ______. Make sure the identical ones open and close balancedly."""

"""And _______________
          ____________
        ______________
                   ___."""

"""
<a>
  <b>
     <c>
       </c>
       </b>
       <c>
        </c>
        </a>  # Why doesn't this close until now? Because the printing is misleading: </8> means the last char ends at the same offset as <7>'s begins. Go back to treating the endpoint index semantically the same as the start point. Giving them different meanings makes the algo messy.
        <c>
        <d>
          </d>
          </c>
          <d>
          <e>
            </e>
            </d>
"""