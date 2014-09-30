"""Routines for handling highlight regions ("extents") during search"""

import cgi


def highlight(content, extents):
    """Return ``content`` with the union of all ``extents`` highlighted.

    Put ``<b>`` before the beginning of each highlight and ``</b>`` at the
    end. Combine overlapping highlights.

    :arg content: The unicode string against which the extents are reported
    :arg extents: An iterable of unsorted, possibly overlapping (start offset,
        end offset) tuples describing each extent to highlight.

    Leading whitespace is stripped.

    """
    def chunks():
        chars_before = None
        for start, end in fix_extents_overlap(sorted(extents)):
            if start > end:
                raise ValueError('Extent start was after its end.')
            yield cgi.escape(content[chars_before:start])
            yield u'<b>'
            yield cgi.escape(content[start:end])
            yield u'</b>'
            chars_before = end
        # Make sure to get the rest of the line after the last highlight:
        yield cgi.escape(content[chars_before:])
    return ''.join(chunks()).lstrip()


def fix_extents_overlap(extents):
    """Take a sorted list of extents and yield the extents without overlaps."""
    # There must be two extents for there to be an overlap
    while len(extents) >= 2:
        # Take the two next extents
        start1, end1 = extents[0]
        start2, end2 = extents[1]
        # Check for overlap
        if end1 <= start2:
            # If no overlap, yield first extent
            yield start1, end1
            extents = extents[1:]  # This has got to be slow as death.
            continue
        # If overlap, yield extent from start1 to start2
        if start1 != start2:
            yield start1, start2
        extents[0] = start2, end1
        extents[1] = end1, end2
    if extents:
        yield extents[0]
