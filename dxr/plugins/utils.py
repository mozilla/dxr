"""Some common utilities used by plugins but _not_ required by the API"""

from collections import namedtuple
from itertools import ifilter, chain, imap, groupby
from operator import itemgetter

from funcy import decorator, is_mapping, flatten

from dxr.plugins import TreeToIndex

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


class TransitionError(Exception):
    """Raised if state transition invariant is broken."""


@decorator
def transition(call, start, end):
    """Assert"""
    self = call._args[0]
    if self.state != start:
        raise TransitionError('In state {0}, expected {1}'.format(
            self.state, start))
    out = call()
    self.state = end
    return out


class StatefulTreeToIndex(TreeToIndex):
    """Start -> Env -> Prebuild -> Postbuild"""
    def __init__(self, tree, state_machine):
        super(StatefulTreeToIndex, self).__init__(tree)
        self.state_machine = state_machine(tree)
        # start coroutine
        next(self.state_machine)
        self.state = "start"

    @transition('start', 'environment')
    def environment(self, vars):
        return self.state_machine.send(vars)

    @transition('environment', 'pre_build')
    def pre_build(self):
        next(self.state_machine)

    @transition('pre_build', 'post_build')
    def post_build(self):
        self.file_indexer = next(self.state_machine)

    @transition('post_build', 'post_build')
    def file_to_index(self, path, contents):
        return self.file_indexer(path=path, contents=contents, tree=self.tree)
