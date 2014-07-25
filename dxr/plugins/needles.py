"""Helper utilities for working with needles."""

from operator import itemgetter
from itertools import chain, repeat, imap, izip


from funcy import group_by


def _unsparsify(annotations):
    """[(line, key, val)] -> [[(key, val)]]"""
    next_unannotated_line = 0
    for line, annotations in groupby(annotations, itemgetter(0)):
        for next_unannotated_line in xrange(next_unannotated_line,
                                            line - 1):
            yield []
        yield [data for _, data in annotations]
        next_unannotated_line = line


def unsparsify(key_val_spans):
    """Transform a sparse needle list [(key:str, val:str, Extent)]
    into proper dense needle format [(key:str, val:str)].

    """
    return _unsparsify(by_line(key_val_spans))


def by_line(key_val_spans):
    """[(key,val,span)] -> [(line, [(key,val)])]
    Groups the key values by line.

    """
    return chain.from_iterable(
        imap(itemgetter(1), span_to_lines(key_val_spans)))


def span_to_lines(key_val_spans):
    """[(key,val,span)] -> [(key,val,line)]
    Converts spans to lines. The resulting iter will have len' >= len.

    """
    key = itemgetter(0)
    return group_by(key, chain.from_iterable(
        imap(_span_to_lines, key_val_spans)), key=key)


def _span_to_lines((key, val, span)):
    return izip(xrange(span.start.row, span.end.row + 1), repeat((key, val)))
