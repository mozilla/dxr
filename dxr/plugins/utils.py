"""Some common utilities used by plugins but _not_ required by the API"""

from collections import namedtuple

Extent = namedtuple('Extent', ['start', 'end'])
# Note that if offset is a Maybe Int, if not present it's None
Position = namedtuple('Position', ['offset', 'row', 'col'])
FuncSig = namedtuple('FuncSig', ['input', 'output'])
Call = namedtuple('Call', ['callee', 'caller', 'calltype'])


def is_function((_, obj)):
    if '!type' not in obj:
        return False
    type_ = obj['!type']
    return hasattr(type_, 'input') and hasattr(type_, 'output')
