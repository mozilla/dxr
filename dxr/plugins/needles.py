"""Helper utilities for working with needles"""

from operator import itemgetter
from itertools import repeat, imap, izip, chain

from funcy import group_by, pluck, decorator


@decorator
def unsparsify_func(call):
    return unsparsify(call())


def unsparsify(span_needles):
    """Transform a sparse needle list [(key, val, span:Extent)]
    into proper dense needle format [[(key, val)]].

    In the dense format, the index, i, specifies the line number from the file.
                         the list at i are all the (key, val) for that line.

    """
    return group_needles(by_line(span_needles))


def group_needles(line_needles):
    """Group line needles by line. [(_, line)] -> [[_]]."""
    grouped_needles = group_by(itemgetter(1), line_needles)
    return pluck(1, sorted(grouped_needles.items(), key=itemgetter(0)))


def by_line(span_needles):
    """Transform [(_, span:Extent)] into [(_, line:int)].

    Converts spans to lines. The resulting iter will have len' >= len.

    """
    return chain.from_iterable(imap(span_to_lines, span_needles))


def span_to_lines((val, span)):
    """Expand (_, span:Extent) into [(_, line:int)]."""
    return izip(repeat(val), xrange(span.start.row, span.end.row + 1))
