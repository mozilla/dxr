"""Helper utilities for working with needles"""

from operator import itemgetter
from itertools import imap

from funcy import group_by, decorator, imapcat


@decorator
def unsparsify_func(call):
    return unsparsify(call())


def unsparsify(span_needles):
    """Transform a sparse needle list [(key, val, span:Extent)] into the
    line-by-line format the plugin API expects: [[(key, (val, line_span))]].

    line_span has the shape (col1, col2).

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
    return ((key_object_pair(*kv_start_end), line_number) for
            kv_start_end, line_number in imapcat(span_to_lines, span_needles))


def key_object_pair((k, v), start, end):
    """Transform a key/value pair, along with start and end columns, to a
    key/multi-propertied-object pair that can be stored in ES and then used
    to support searching and highlighting.

    """
    return k, {'value': v, 'start': start, 'end': end}


def span_to_lines((kv, span)):
    """Expand ((k, v), span:Extent) into [(((k, v), line_span), line:int)].

    line_span has shape: (col1, col2)

    """
    if span.end.row == span.start.row:
        yield (kv, span.start.col, span.end.col), span.start.row

    elif span.end.row < span.start.row:
        raise ValueError("end.row < start.row")

    else:
        # TODO: There are a lot of Nones used as slice bounds below. Do we
        # ever translate them back into char offsets? If not, does the
        # highlighter or anything else choke on them?
        yield (kv, span.start.col, None), span.start.row

        # Really wish we could use yield from
        for row in xrange(span.start.row + 1, span.end.row):
            yield (kv, 0, None), row

        yield (kv, 0, span.end.col), span.end.row
