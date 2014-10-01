"""Some common utilities used by plugins but _not_ required by the API"""

from collections import namedtuple
from operator import itemgetter

from dxr.plugins import Filter, negatable


Extent = namedtuple('Extent', ['start', 'end'])  # 0-based
# Note that if offset is a Maybe Int, if not present it's None
Position = namedtuple('Position', ['offset', 'row', 'col'])  # offset & col 0-based, row 1-based
Call = namedtuple('Call', ['callee', 'caller', 'calltype'])


class FuncSig(namedtuple('FuncSig', ['inputs', 'output'])):
    def __str__(self):
        return '{0} -> {1}'.format(
            tuple(self.inputs), self.output).replace("'", '').replace('"', '')


class ExactMatchExtentFilterBase(Filter):
    """Filter for a compound needle which tries to find an exact match on a
    'value' subproperty and highlights based on 'start' and 'end'
    subproperties, which contain column bounds.

    Will highlight and filter based on the field_name cls attribute.

    """
    def __init__(self, term):
        """Expects ``self.lang`` to be a language identifier, to separate
        structural needles form those of other languages and allow for an
        eventual "lang:" metafilter.

        """
        super(ExactMatchExtentFilterBase, self).__init__(term)
        self._needle = '{0}-{1}'.format(self.lang, self.name)

    @negatable
    def filter(self):
        # TODO: case, fully qualified
        return {
            'term': {'{0}.value'.format(self._needle): self._term['arg']}
        }

    def highlight_content(self, result):
        # TODO: Update for case, qualified, etc.
        if self._term['not']:
            return []
        return ((entity['start'], entity['end'])
                for entity in result[self._needle]
                if entity['value'] == self._term['arg'])
