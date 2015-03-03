import ast, tokenize, token
from StringIO import StringIO

from dxr.indexers import (FileToIndex as FileToIndexBase, Extent, Position,
                          iterable_per_line, with_start_and_end, split_into_lines)
from dxr.filters import LINE


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
        ast.ClassDef: 'py_type',
        ast.FunctionDef: 'py_function',
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
        # AST nodes for classes and functions point to the position of
        # their 'def' and 'class' tokens. To get the position of their
        # names, we look for 'def' and 'class' tokens and store the
        # position of the token immediately following them.
        node_start_table = {}
        previous_start = None
        token_gen = tokenize.generate_tokens(StringIO(self.contents).readline)
        for tok_type, tok_name, start, end, _ in token_gen:
            if tok_type != token.NAME:
                continue

            if tok_name in ('def', 'class'):
                previous_start = start
            elif previous_start is not None:
                node_start_table[previous_start] = start
                previous_start = None

        # Run through the AST looking for things to index!
        syntax_tree = ast.parse(self.contents.encode('utf-8'))
        for node in ast.walk(syntax_tree):
            if isinstance(node, ast.ClassDef) or isinstance(node, ast.FunctionDef):
                node.start = (node.lineno, node.col_offset)
                if node.start in node_start_table:
                    node.start = node_start_table[node.start]

                node.end = (node.start[0], node.start[1] + len(node.name))
                needle_type = self.needle_types[node.__class__]
                yield self._needle(needle_type, node.name, node.start, node.end)

    def _needle(self, needle_type, name, start, end):
        return (
            needle_type,
            {'name': name,
             'start': start[1],
             'end': end[1]},
            Extent(Position(row=start[0],
                            col=start[1]),
                   Position(row=end[0],
                            col=end[1]))
        )
