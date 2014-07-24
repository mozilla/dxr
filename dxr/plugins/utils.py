"""Some common utilities used by plugins but _not_ required by the API"""

from collections import namedtuple
from itertools import ifilter

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


@decorator
def transition(call, start, end):
    self = call._args[0]
    if self.state != start:
        raise RuntimeError('In state {0}, expected {1}'.format(
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


def get_needles(condense, *args):
    """Return list of unsparsified needles by line."""
    sparse_needles = chain((to_needles(condense, arg) for arg in args))
    return unsparsify_spans(sparse_needles)
