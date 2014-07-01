"""Some common utilities used by plugins but _not_ required by the API"""

from collections import namedtuple
from itertools import ifilter

Extent = namedtuple('Extent', ['start', 'end'])
Position = namedtuple('Position', ['offset', 'row', 'col'])
FuncSig = namedtuple('FuncSig', ['input', 'output'])

def symbols(condensed):
    """Return a dict, (symbol name) -> (dict of fields and metadata)."""
    queue = condensed.items()
    while queue:
        key, val = queue.pop()
        if key.startswith('!'):
            continue
        yield key, val
        if hasattr(val, 'items'):
            queue.extend(val.items())


def functions(condensed):
    """Return an iterator of pairs (symbol, val) if the symbol is a function."""
    return ifilter(is_function, symbols(condensed))


def is_function((_, obj)):
    if '!type' not in obj:
        return False
    type_ = obj['!type']
    return hasattr(type_, 'input') and hasattr(type_, 'output')
