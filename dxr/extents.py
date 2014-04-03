"""Routines for handling highlight regions ("extents") during search"""

import cgi
from itertools import groupby, izip
import struct


# groupby(line, results) --> merge, uniquify, sort, and non-overlap extents --> grouby(file) --> highlight_lines


def unpack_trilite_extents(trg_extents):
    """Turn a binary extent blob from trilite into an iterable of (start, end)
    pairs."""
    for i in xrange(0, len(trg_extents), 8):
        yield struct.unpack('II', trg_extents[i:i+8])


def union_extents(tuples):
    """Return an iterable of (start, end) from an iterable of (packed
    trg_extents, [extent1_start, extent1_end, extent2_start, ...]).

    Returned extents may be out of order and include duplicates.

    """
    for trg_extents, other_extents in tuples:
        for e in unpack_trilite_extents(trg_extents or ()):
            yield e
        # Turn other extents into an iterable of (start, end) tuples:
        for e in izip(other_extents[::2], other_extents[1::2]):
            yield e


def flatten_extents(cursor):
    """Given a raw set of search results from the DB, merge the rows that
    reference the same line of a file, and combine their extents, yielding
    (everything, extents) for each line.

    This handles the situation where there are, say, a var ref is searched
    for, and 2 refs occur on the same line, yielding 2 rows.

    """
    # For each group of results representing a single line...
    for line_id, results in groupby(cursor, lambda r: r['line_id']):
        # Buffer all results for this line so unique_extents() and such
        # don't have to complicate themselves by preserving things other
        # than extents.
        line_results = list(results)

        # Grab a unified list of extents for all occurrences of this line:
        extents = union_extents((r[7], tuple(r)[8:]) for r in line_results)

        # TODO: Nones used to occur in the DB. Is this still true? Filter them
        # out if so.

        # Uniquify, sort, and fix overlaps:
        extents = list(set(extents))
        extents.sort()
        extents = fix_extents_overlap(extents)

        yield line_results[0], extents


def highlight_line(content, extents, markup, markdown, encoding):
    """Return the line of text ``content`` with the given ``extents`` prefixed
    by ``markup`` and suffixed by ``markdown``.

    :arg content: The contents of the file against which the extents are
        reported, as a bytestring. (We need to operate in terms of bytestrings,
        because those are the terms in which the C compiler gives us extents.)
    :arg extents: A sequence of non-overlapping (start offset, end offset)
        tuples describing each extent to highlight. The sequence must be in
        order by start offset.
    :arg encoding: The encoding with which to decode the bytestring

    We assume that none of the extents split a multibyte character. Leading
    whitespace is stripped.

    """
    def chunks():
        chars_before = None
        for start, end in extents:
            yield cgi.escape(content[chars_before:start].decode(encoding,
                                                                'replace'))
            yield markup
            yield cgi.escape(content[start:end].decode(encoding, 'replace'))
            yield markdown
            chars_before = end
        # Make sure to get the rest of the line after the last highlight:
        yield cgi.escape(content[chars_before:].decode(encoding, 'replace'))
    return ''.join(chunks()).lstrip()


class genWrap(object):   # XXX: Delete?
    """Auxiliary class for wrapping a generator and make it nicer"""
    def __init__(self, gen):
        self.gen = gen
        self.value = None
    def next(self):
        try:
            self.value = self.gen.next()
            return True
        except StopIteration:
            self.value = None
            return False


def merge_extents(*elist):   # XXX: Delete?
    """
        Take a list of extents generators and merge them into one stream of extents
        overlapping extents will be split in two, this means that they will start
        and stop at same location.
        Here we assume that each extent is a triple as follows:
            (start, end, keyset)

        Where keyset is a list of something that should be applied to the extent
        between start and end.
    """
    elist = [genWrap(e) for e in elist]
    elist = [e for e in elist if e.next()]
    while len(elist) > 0:
        start = min((e.value[0] for e in elist))
        end = min((e.value[1] for e in elist if e.value[0] == start))
        keylist = []
        for e in (e for e in elist if e.value[0] == start):
            for k in e.value[2]:
                if k not in keylist:
                    keylist.append(k)
            e.value = (end, e.value[1], e.value[2])
        yield start, end, keylist
        elist = [e for e in elist if e.value[0] < e.value[1] or e.next()]


def fix_extents_overlap(extents):
    """
        Take a sorted list of extents and yield the extents without overlapings.
        Assumes extents are of similar format as in merge_extents
    """
    # There must be two extents for there to be an overlap
    while len(extents) >= 2:
        # Take the two next extents
        start1, end1 = extents[0]
        start2, end2 = extents[1]
        # Check for overlap
        if end1 <= start2:
            # If no overlap, yield first extent
            yield start1, end1
            extents = extents[1:]
            continue
        # If overlap, yield extent from start1 to start2
        if start1 != start2:
            yield start1, start2
        extents[0] = start2, end1
        extents[1] = end1, end2
    if extents:
        yield extents[0]
