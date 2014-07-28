"""Some common utilities used by plugins but _not_ required by the API"""

from collections import namedtuple


Extent = namedtuple('Extent', ['start', 'end'])
# Note that if offset is a Maybe Int, if not present it's None
Position = namedtuple('Position', ['offset', 'row', 'col'])
Call = namedtuple('Call', ['callee', 'caller', 'calltype'])


class FuncSig(namedtuple('FuncSig', ['inputs', 'output'])):
    def __init__(self, inputs, output):
        super(FuncSig, self).__init__(self, inputs, output)

    def __str__(self):
        return '{0} -> {1}'.format(
            tuple(self.inputs), self.output).replace("'", '').replace('"', '')


def _process_ctype(type_):
    return type_


def c_type_sig(inputs, output, method=None):
    inputs = remove(lambda x: x == "void", inputs) # Void Elimination

    inputs = map(lambda x: x.replace(' ', ''), inputs)
    output = output.replace(' ', '')

    if method is not None:
        inputs = [method] + inputs

    if len(inputs) == 0:
        inputs = ["void"]

    return FuncSig(tuple(inputs), output)


def is_function((_, obj)):
    if '!type' not in obj:
        return False
    type_ = obj['!type']
    return hasattr(type_, 'input') and hasattr(type_, 'output')
