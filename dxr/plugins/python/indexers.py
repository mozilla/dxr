import ast, tokenize, token
from StringIO import StringIO

from dxr.indexers import (FileToIndex as FileToIndexBase, Extent, Position,
                          iterable_per_line, with_start_and_end, split_into_lines)
from dxr.filters import LINE


PLUGIN_NAME = 'python'


NEEDLE = {
    'type': 'object',
    'properties': {
        'name': {
            'type': 'string',
            'index': 'not_analyzed',
            'fields': {
                'lower': {
                    'type': 'string',
                    'analyzer': 'lowercase'
                }
            }
        },
        'start': {
            'type': 'integer',
            'index': 'no'  # just for highlighting
        },
        'end': {
            'type': 'integer',
            'index': 'no'
        }
    }
}

mappings = {
    LINE: {
        'properties': {
            'py_type': NEEDLE,
            'py_function': NEEDLE,
        },
    },
}


class FileToIndex(FileToIndexBase):
    needle_types = {
        'ClassDef': 'py_type',
        'FunctionDef': 'py_function',
    }

    def is_interesting(self):
        return self.path.endswith('.py')

    def needles_by_line(self):
        return iterable_per_line(
            with_start_and_end(
                split_into_lines(
                    self._all_needles()
                )
            )
        )

    def _all_needles(self):
        """Return an iterable of needles in (needle name, value, Extent) format."""

        syntax_tree = ast.parse(self.contents.encode('utf-8'))

        # Create a lookup table for ast nodes by lineno and
        # col_offset, for those that have them.  This makes it easy to
        # associate nodes with their corresponding token.
        node_location = {}
        for node in ast.walk(syntax_tree):
            if getattr(node, 'lineno', None) is not None:
                position = (node.lineno, node.col_offset)
                node_location.setdefault(position, []).append(node)

        tmpfile = StringIO(self.contents)
        token_gen = tokenize.generate_tokens(tmpfile.readline)

        relocate_nodes = []
        for tok_type, tok_name, start, end, _ in token_gen:
            if tok_type != token.NAME:
                relocate_nodes = []
                continue

            cur_token = {'name': tok_name, 'start': start, 'end': end}
            if relocate_nodes:
                cur_token['nodes'] = relocate_nodes
            else:
                cur_token['nodes'] = node_location.get(start, [])

            relocate_nodes = []

            # The ast node has a lineno and col_offset that points to
            # where the token 'def' or 'class' is positioned in the file.
            # We actually want it to go with the following name token.
            if tok_type == token.NAME and tok_name in ('def', 'class'):
                relocate_nodes, cur_token['nodes'] = cur_token['nodes'], []

            if cur_token.get('nodes'):
                needle = self._construct_needle(cur_token)
                if needle:
                    yield needle

    def _construct_needle(self, tok):
        class_name = tok['nodes'][0].__class__.__name__
        needle_type = self.needle_types.get(class_name)

        if needle_type:
            return (
                needle_type,
                {'name': tok['name'],
                 'start': tok['start'][1],
                 'end': tok['end'][1]},
                Extent(Position(row=tok['start'][0],
                                col=tok['start'][1]),
                       Position(row=tok['end'][0],
                                col=tok['end'][1]))
            )
