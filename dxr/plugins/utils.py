"""Some common utilities used by plugins but _not_ required by the API"""

from collections import namedtuple
from dxr.plugins import LINE


Extent = namedtuple('Extent', ['start', 'end'])
# Note that if offset is a Maybe Int, if not present it's None
Position = namedtuple('Position', ['offset', 'row', 'col'])
Call = namedtuple('Call', ['callee', 'caller', 'calltype'])


class FuncSig(namedtuple('FuncSig', ['inputs', 'output'])):
    def __str__(self):
        return '{0} -> {1}'.format(
            tuple(self.inputs), self.output).replace("'", '').replace('"', '')


def _process_ctype(type_):
    return type_


def is_function((_, obj)):
    if '!type' not in obj:
        return False
    type_ = obj['!type']
    return hasattr(type_, 'input') and hasattr(type_, 'output')


def needle_filter_factory(lang, tag):
    class NeedleFilter(object):
        name = tag
        domain = LINE
        field_name = "{0}-{1}".format(lang, tag)
        
        def __init__(self, term):
            self.term = term

        def filter(self):
            return {
                "filtered": {
                    "term": {
                        field_name: self.term
                    }
                }
            }

        def highlight(self, result):
            c1, c2 = result['loc']
            if c2 is None:
                c2 = len(result['content'])
            return {
                field_name: [(c1, c2)]
            }
    return needle_filter_factory
