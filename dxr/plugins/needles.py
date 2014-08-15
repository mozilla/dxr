"""Helper utilities for working with needles"""

from operator import itemgetter
from itertools import repeat, imap, izip, chain

from funcy import group_by, pluck, decorator, imapcat


@decorator
def unsparsify_func(call):
    return unsparsify(call())


def unsparsify(span_needles):
    """Transform a sparse needle list [(key, val, span:Extent)]
    into proper dense needle format [[(key, (val, line_span))]].

    line_span has shape: (col1, col2)

    In the dense format, the index, i, specifies the line number from the file.
                         the list at i are all the (key, val) for that line.

    """
    return group_needles(by_line(span_needles))


def group_needles(line_needles):
    """Group line needles by line. [(_, line)] -> [[_]]."""
    grouped_needles = sorted(group_by(itemgetter(1), line_needles).iteritems(),
                             key=itemgetter(0))
    return [map(itemgetter(0), ndl) for ndl in pluck(1, grouped_needles)]


def by_line(span_needles):
    """Transform [(_, span:Extent)] into [(_, line:int)].

    Converts spans to lines. The resulting iter will have len' >= len.

    """
    return imapcat(span_to_lines, span_needles)


def span_to_lines((val, span)):
    """Expand (_, span:Extent) into [((_, line_span), line:int)].

    line_span has shape: (col1, col2)

    """
    if span.end.row == span.start.row:
        yield (val, (span.start.col, span.end.col)), span.start.row

    elif span.end.row < span.start.row:
        raise UnOrderedRowError

    else:
        yield (val, (span.start.col, None)), span.start.row

        # Really with we could use yield from
        for row in xrange(span.start.row + 1, span.end.row):
            yield ((val, (0, None)), row)

        yield ((val, (0, span.end.col)), span.end.row)


class UnOrderedRowError(Exception):
    """Raised iff the end.row < start.row."""
