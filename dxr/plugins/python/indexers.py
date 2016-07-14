import ast
import token
import tokenize
from os.path import islink
from StringIO import StringIO
from itertools import izip

from dxr.build import unignored
from dxr.filters import FILE, LINE
from dxr.indexers import (Extent, FileToIndex as FileToIndexBase,
                          iterable_per_line, Position, split_into_lines,
                          TreeToIndex as TreeToIndexBase,
                          QUALIFIED_FILE_NEEDLE, QUALIFIED_LINE_NEEDLE,
                          with_start_and_end)
from dxr.plugins.python.analysis import TreeAnalysis
from dxr.plugins.python.menus import ClassRef
from dxr.plugins.python.utils import (ClassFunctionVisitorMixin,
                                      convert_node_to_name, local_name,
                                      path_to_module, ast_parse)


mappings = {
    FILE: {
        'properties': {
            'py_module': QUALIFIED_FILE_NEEDLE,
        },
    },
    LINE: {
        'properties': {
            'py_type': QUALIFIED_LINE_NEEDLE,
            'py_function': QUALIFIED_LINE_NEEDLE,
            'py_derived': QUALIFIED_LINE_NEEDLE,
            'py_bases': QUALIFIED_LINE_NEEDLE,
            'py_callers': QUALIFIED_LINE_NEEDLE,
            'py_overrides': QUALIFIED_LINE_NEEDLE,
            'py_overridden': QUALIFIED_LINE_NEEDLE,
        },
    },
}


class _FileToIgnore(object):
    """A file that we don't want to bother indexing, usually due to
    syntax errors.

    """
    def is_interesting(self):
        return False
FILE_TO_IGNORE = _FileToIgnore()


class TreeToIndex(TreeToIndexBase):
    @property
    def unignored_files(self):
        return unignored(self.tree.source_folder, self.tree.ignore_paths,
                         self.tree.ignore_filenames)

    def post_build(self):
        paths = ((path, self.tree.source_encoding)
                 for path in self.unignored_files if is_interesting(path))
        self.tree_analysis = TreeAnalysis(
            python_path=self.plugin_config.python_path,
            source_folder=self.tree.source_folder,
            paths=paths)

    def file_to_index(self, path, contents):
        if path in self.tree_analysis.ignore_paths:
            return FILE_TO_IGNORE
        else:
            return FileToIndex(path, contents, self.plugin_name, self.tree,
                               tree_analysis=self.tree_analysis)


class IndexingNodeVisitor(ast.NodeVisitor, ClassFunctionVisitorMixin):
    """Node visitor that walks through the nodes in an abstract syntax
    tree and finds interesting things to index.

    """

    def __init__(self, file_to_index, tree_analysis):
        super(IndexingNodeVisitor, self).__init__()

        self.file_to_index = file_to_index
        self.tree_analysis = tree_analysis
        self.needles = []
        self.refs = []

    def visit_Name(self, node):
        self.file_to_index.advance_node(node)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        self.file_to_index.advance_node(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Index the function itself for the function: filter.
        start, end = self.file_to_index.get_node_start_end(node)
        if start is not None:
            self.yield_needle('py_function', node.name, start, end)

        super(IndexingNodeVisitor, self).visit_FunctionDef(node)

    def visit_Call(self, node):
        # Index function/method call sites
        name = convert_node_to_name(node.func)
        if name:
            start, end = self.file_to_index.get_node_start_end(node)
            if start is not None:
                self.yield_needle('py_callers', name, start, end)

        self.generic_visit(node)

    def visit_ClassDef(self, node):
        # Index the class itself for the type: filter.
        start, end = self.file_to_index.get_node_start_end(node)
        if start is not None:
            self.yield_needle('py_type', node.name, start, end)

            # Index the class hierarchy for classes for the derived: and
            # bases: filters.
            class_name = self.get_class_name(node)

            bases = self.tree_analysis.get_base_classes(class_name,
                                                        set([class_name]))
            for qualname in bases:
                self.yield_needle(needle_type='py_derived',
                                  name=local_name(qualname), qualname=qualname,
                                  start=start, end=end)

            derived_classes = self.tree_analysis.get_derived_classes(class_name,
                                                                     set([class_name]))
            for qualname in derived_classes:
                self.yield_needle(needle_type='py_bases',
                                  name=local_name(qualname), qualname=qualname,
                                  start=start, end=end)

            # Show a menu when hovering over this class.
            self.yield_ref(start, end,
                           ClassRef(self.file_to_index.tree, class_name))

        super(IndexingNodeVisitor, self).visit_ClassDef(node)

    def visit_ClassFunction(self, class_node, function_node):
        class_name = self.get_class_name(class_node)
        function_qualname = class_name + '.' + function_node.name
        start, end = self.file_to_index.get_node_start_end(function_node)
        if start is None:
            return

        # Index this function as being overridden by other functions for
        # the overridden: filter.
        for qualname in self.tree_analysis.overridden_functions[function_qualname]:
            name = qualname.rsplit('.')[-1]
            self.yield_needle(needle_type='py_overridden',
                              name=name, qualname=qualname,
                              start=start, end=end)

        # Index this function as overriding other functions for the
        # overrides: filter.
        for qualname in self.tree_analysis.overriding_functions[function_qualname]:
            name = qualname.rsplit('.')[-1]
            self.yield_needle(needle_type='py_overrides',
                              name=name, qualname=qualname,
                              start=start, end=end)

    def get_class_name(self, class_node):
        return self.file_to_index.abs_module_name + '.' + class_node.name

    def yield_needle(self, *args, **kwargs):
        needle = line_needle(*args, **kwargs)
        self.needles.append(needle)

    def yield_ref(self, start, end, ref):
        self.refs.append((
            self.file_to_index.char_offset(*start),
            self.file_to_index.char_offset(*end),
            ref,
        ))


class FileToIndex(FileToIndexBase):
    def __init__(self, path, contents, plugin_name, tree, tree_analysis):
        """
        :arg tree_analysis: TreeAnalysisResult object with the results
            from the post-build analysis.

        """
        super(FileToIndex, self).__init__(path, contents, plugin_name, tree)

        self.tree_analysis = tree_analysis
        self.abs_module_name = path_to_module(tree_analysis.python_path, self.path)

        self._visitor = None

    def is_interesting(self):
        return super(FileToIndex, self).is_interesting() and is_interesting(self.path)

    @property
    def visitor(self):
        """Return IndexingNodeVisitor for this file, lazily creating and
        running it if it doesn't exist yet.

        """
        if not self._visitor:
            self.node_start_table = self.analyze_tokens()
            self._visitor = IndexingNodeVisitor(self, self.tree_analysis)
            syntax_tree = ast_parse(self.contents)
            self._visitor.visit(syntax_tree)
        return self._visitor

    def needles(self):
        # Index module name. For practical purposes, this includes
        # __init__.py files for packages even though that's not
        # _technically_ a module.
        yield file_needle('py_module',
                          name=local_name(self.abs_module_name),
                          qualname=self.abs_module_name)

    def needles_by_line(self):
        return iterable_per_line(
            with_start_and_end(
                split_into_lines(
                    self.visitor.needles
                )
            )
        )

    def refs(self):
        return self.visitor.refs

    def analyze_tokens(self):
        """Split the file into tokens and analyze them for data needed
        for indexing.

        """
        # Run the file contents through the tokenizer, both as unicode
        # and as a utf-8 encoded string.  This will allow us to build
        # up a mapping between the byte offset and the character offset.
        token_gen = tokenize.generate_tokens(StringIO(self.contents).readline)
        utf8_token_gen = tokenize.generate_tokens(
            StringIO(self.contents.encode('utf-8')).readline)

        # This is a mapping from the utf-8 byte starting points provided by
        # the ast nodes, to a list of the unicode character offset tuples for
        # both the start and the end points of the actual tokens.  Attribute
        # ast nodes wind up with the same lineno and col_offset as the object
        # they are attributes of, so store all of the offsets in a list.
        node_start_table = {}

        paren_level, paren_stack = 0, {}

        for unicode_token, utf8_token in izip(token_gen, utf8_token_gen):
            tok_type, tok_name, start, end, _ = unicode_token
            utf8_start = utf8_token[2]

            if tok_type == token.NAME:
                # AST nodes for classes and functions point to the position of
                # their 'def' and 'class' tokens. To get the position of their
                # names, we start the queue for the current parenthesis level
                # at the byte offset for the keyword token, but only start
                # pushing character offsets once we're past the keyword.
                paren_stack.setdefault(paren_level, (utf8_start, []))

                if tok_name not in ('def', 'class'):
                    paren_stack[paren_level][1].append((start, end))

                continue

            elif tok_type == token.OP:
                # Container delimiters (parens, brackets, and braces) start a
                # new context where the node for following name tokens will no
                # longer be tied to the position of the head of the current
                # queue.  So, keep track of the current context with a stack,
                # here implemented with a dict so that it can be sparse.
                if tok_name in '([{':
                    paren_level += 1
                elif tok_name in '}])':
                    node_start, node_queue = paren_stack.pop(paren_level, (None, None))
                    if node_start is not None:
                        node_start_table[node_start] = node_queue
                    paren_level -= 1
                elif tok_name == '.':
                    # Attribute access.  Don't reset, stay at the same level.
                    pass
                else:
                    node_start, node_queue = paren_stack.pop(paren_level, (None, None))
                    if node_start is not None:
                        node_start_table[node_start] = node_queue

            elif tok_type == token.NEWLINE:
                node_start, node_queue = paren_stack.pop(paren_level, (None, None))
                if node_start is not None:
                    node_start_table[node_start] = node_queue

        return node_start_table

    def get_node_start_end(self, node):
        """Return start and end positions within the file for the given
        AST Node.

        """
        loc = node.lineno, node.col_offset

        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.Call)):
            loc_list = self.node_start_table.get(loc, [])
            if loc_list:
                return loc_list[-1]

        return None, None

    def advance_node(self, node):
        """Destructively change which actual token offset we'll get on a call
        to get_node_start_end.

        """
        loc = node.lineno, node.col_offset
        try:
            self.node_start_table[loc].pop()
        except Exception:
            pass


def file_needle(needle_type, name, qualname=None):
    data = {'name': name}
    if qualname:
        data['qualname'] = qualname

    return needle_type, data


def line_needle(needle_type, name, start, end, qualname=None):
    data = {
        'name': name,
        'start': start[1],
        'end': end[1]
    }

    if qualname:
        data['qualname'] = qualname

    return (
        needle_type,
        data,
        Extent(Position(row=start[0],
                        col=start[1]),
               Position(row=end[0],
                        col=end[1]))
    )


def is_interesting(path):
    """Determine if the file at the given path is interesting enough to
    analyze.

    """
    return path.endswith('.py') and not islink(path)
