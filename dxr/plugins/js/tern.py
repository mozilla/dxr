from operator import itemgetter
from itertools import chain, repeat, groupby, imap, izip

from .condense import functions, symbols, properties


def unsparsify(annotations):
    """[(line, key, val)] -> [[(key, val)]]"""
    next_unannotated_line = 0
    for line, annotations in groupby(annotations, itemgetter(0)):
        for next_unannotated_line in xrange(next_unannotated_line,
                                            line - 1):
            yield []
        yield [data for line_num, data in annotations]
        next_unannotated_line = line


def unsparsify_spans(key_val_spans):
    return unsparsify(by_line(key_val_spans))


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
    return groupby(sorted(chain.from_iterable(
        imap(_span_to_lines, key_val_spans)), key=key), key)


def _span_to_lines((key, val, span)):
    return izip(xrange(span.start.row, span.end.row + 1), repeat((key, val)))


def function_needles_sparse(condensed):
    return (('js-function', name, props['!span']) for name, props
            in functions(condensed))


def symbol_needles_sparse(condensed):
    return (('js-symbol', name, props['!span']) for name, props
            in symbols(condensed))


def property_needles_sparse(condensed):
    return (('js-property', name, span) for _, name, span
            in properties(condensed))


def get_needles(condensed):
    """From a condensed output, return all needles for the plugin interface."""
    sparse_needles = chain(function_needles_sparse(condensed),
                           symbol_needles_sparse(condensed),
                           property_needles_sparse(condensed))

    return unsparsify_spans(sparse_needles)
