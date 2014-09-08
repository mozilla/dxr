"""Some common utilities used by plugins but _not_ required by the API"""

from collections import namedtuple
from operator import itemgetter

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


class NeedleFilter(object):
    """Filter for a simple needle.

    Will highlight and filter based on the field_name cls attribute.

    """
    lang = ''
    name = ''
    domain = LINE
    description = ''

    def __init__(self, term):
        self.term = term
        self.field_name = '{0}-{1}'.format(self.lang, self.name)

    def filter(self):
        # TODO use self.field_name to select which term to filter for
        return {}

    def highlight(self, result, field):
        content = result['content']
        def _highlight(needle):
            return needle['start'], needle['end'] or len(content)

        highlights = sorted((_highlight(needle) for needle
                             in content[field]
                             if content['term'] == self.term),
                            key=itemgetter('start'))
        return {'content': highlights}
