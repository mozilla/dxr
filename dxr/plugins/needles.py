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
    """Group line needles by line, and return a list of needles for each line,
    up to the last line with any needles::

        [(a, 1), (b, 4), (c, 4)] -> [[a], [], [], [b, c]]

    """
    # Jam all the needles of a file into a hash by line number:
    line_map = group_by(itemgetter(1), line_needles)  # {line: needles}
    last_line = max(line_map.iterkeys()) + 1 if line_map else 1

    # Pull out the needles for each line, stripping off the line number
    # elements of the tuples and producing a blank list for missing lines.
    # (The defaultdict returned from group_by takes care of the latter.)
    return [[pair for (pair, _) in line_map[line_num]]
            for line_num in xrange(1, last_line)]


def by_line(span_needles):
    """Transform [(_, span:Extent)] into [(_, line:int)].

    Converts spans to lines. The resulting iter will have len' >= len.

    """
    return imapcat(span_to_lines, span_needles)


def pack((key, value), start, end):
    """Transform a key/value pair, along with start and end columns, to a
    key/value pair that can be stored in ES.

    """
    return key, {'value': value, 'start': start, 'end': end}


def span_to_lines((val, span)):
    """Expand (_, span:Extent) into [((_, line_span), line:int)].

    line_span has shape: (col1, col2)

    """
    if span.end.row == span.start.row:
        yield pack(val, span.start.col, span.end.col), span.start.row

    elif span.end.row < span.start.row:
        raise ValueError("end.row < start.row")

    else:
        yield pack(val, span.start.col, None), span.start.row

        # Really wish we could use yield from
        for row in xrange(span.start.row + 1, span.end.row):
            yield (pack(val, 0, None), row)

        yield (pack(val, 0, span.end.col), span.end.row)
