import ast
import os
import token
import tokenize
from collections import defaultdict
from StringIO import StringIO
from warnings import warn

from dxr.build import file_contents, unignored
from dxr.indexers import (Extent, FileToIndex as FileToIndexBase,
                          iterable_per_line, Position, split_into_lines,
                          TreeToIndex as TreeToIndexBase,
                          QUALIFIED_NEEDLE, with_start_and_end)
from dxr.filters import LINE


mappings = {
    LINE: {
        'properties': {
            'py_type': QUALIFIED_NEEDLE,
            'py_function': QUALIFIED_NEEDLE,
            'py_derived': QUALIFIED_NEEDLE,
            'py_bases': QUALIFIED_NEEDLE,
            'py_callers': QUALIFIED_NEEDLE,
            'py_called_by': QUALIFIED_NEEDLE,
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
    def __init__(self, *args, **kwargs):
        super(TreeToIndex, self).__init__(*args, **kwargs)

        self.python_path = self.plugin_config.python_path

        # Post-build analysis results.
        self.base_classes = defaultdict(list)
        self.derived_classes = defaultdict(list)
        self.names = {}
        self.ignore_paths = set()

    @property
    def unignored_files(self):
        return unignored(self.tree.source_folder, self.tree.ignore_paths,
                         self.tree.ignore_filenames)

    def post_build(self):
        for path in self.unignored_files:
            if is_interesting(path):
                self.analyze(path)

        # Once we've got all the base classes, store the opposite
        # direction: derived classes!
        for class_name, bases in self.base_classes.iteritems():
            for base_name in bases:
                base_name = normalize_name(self.names, base_name)
                self.derived_classes[base_name].append(class_name)

    def analyze(self, path):
        """Parse a Python file and analyze it for import and class data
        that we need to find the inheritance tree for classes later on.

        Stores the results in self.base_classes and self.names.

        """
        module_path = path_to_module(self.python_path, path)

        try:
            syntax_tree = ast.parse(file_contents(path, self.tree.source_encoding))
        except SyntaxError as err:
            rel_path = os.path.relpath(path, self.tree.source_folder)
            warn('Failed to analyze {filename} due to error "{error}".'.format(
                 filename=rel_path, error=err))
            self.ignore_paths.add(rel_path)
            return

        for node in ast.walk(syntax_tree):
            # Save the base classes of any class we find.
            if isinstance(node, ast.ClassDef):
                class_path = module_path + '.' + node.name
                bases = []
                for base in node.bases:
                    base_name = convert_node_to_name(base)
                    if base_name:
                        bases.append(module_path + '.' + base_name)
                self.base_classes[class_path] = bases

            # Whenever we import something, remember the local name
            # of what was imported and where it actually lives.
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    absolute_local_name = module_path + '.' + local_name

                    import_name = alias.name
                    if isinstance(node, ast.ImportFrom):
                        # `from . import x` means node.module is None.
                        if node.module:
                            import_name = node.module + '.' + import_name
                        else:
                            package_path = package_for_module(module_path)
                            if package_path:
                                import_name = package_path + '.' + import_name

                    self.names[absolute_local_name] = import_name

    def file_to_index(self, path, contents):
        if path in self.ignore_paths:
            return FILE_TO_IGNORE
        else:
            return FileToIndex(path, contents, self.plugin_name, self.tree,
                               self.python_path, self.base_classes,
                               self.derived_classes, self.names)


class IndexingNodeVisitor(ast.NodeVisitor):
    """Node visitor that walks through the nodes in an abstract syntax
    tree and finds interesting things to index.

    """

    def __init__(self, file_to_index):
        self.file_to_index = file_to_index
        self.function_call_stack = []  # List of lists of function names.
        self.needles = None

    def get_needles(self, node):
        """Walk through the given AST and return needles to index from
        the tree.

        """
        self.needles = []
        self.visit(node)
        return self.needles

    def visit_FunctionDef(self, node):
        # Index the function itself for the function: filter.
        start, end = self.file_to_index.get_node_start_end(node)
        self.yield_needle('py_function', node.name, start, end)

        # Index function calls within this function for the callers: and
        # called-by filters.
        self.function_call_stack.append([])
        self.generic_visit(node)
        call_needles = self.function_call_stack.pop()
        for name, call_start, call_end in call_needles:
            self.yield_needle('py_callers', name, start, end)
            self.yield_needle('py_called_by', node.name, call_start, call_end)

    def visit_Call(self, node):
        # Save this call if we're currently tracking function calls.
        if self.function_call_stack:
            call_needles = self.function_call_stack[-1]
            name = convert_node_to_name(node.func)
            if name:
                start, end = self.file_to_index.get_node_start_end(node)
                call_needles.append((name, start, end))

        self.generic_visit(node)

    def visit_ClassDef(self, node):
        # Index the class itself for the type: filter.
        start, end = self.file_to_index.get_node_start_end(node)
        self.yield_needle('py_type', node.name, start, end)

        # Index the class hierarchy for classes for the derived: and
        # bases: filters.
        class_name = self.file_to_index.module_name + '.' + node.name

        # Index both the full absolute base name and the
        # local name for conveniece.
        bases = self.file_to_index.get_bases_for_class(class_name)
        for qualname in bases:
            name = qualname.split('.')[-1]
            self.yield_needle(needle_type='py_derived',
                              name=name, qualname=qualname,
                              start=start, end=end)

        derived_classes = self.file_to_index.get_derived_for_class(class_name)
        for qualname in derived_classes:
            name = qualname.split('.')[-1]
            self.yield_needle(needle_type='py_bases',
                              name=name, qualname=qualname,
                              start=start, end=end)

        self.generic_visit(node)

    def yield_needle(self, *args, **kwargs):
        needle = line_needle(*args, **kwargs)
        self.needles.append(needle)


class FileToIndex(FileToIndexBase):
    def __init__(self, path, contents, plugin_name, tree, python_path,
                 class_bases, derived_classes, names):
        """
        :arg python_path: Absolute path to the root folder where Python
        modules for the tree are stored.

        :arg class_bases: Dictionary mapping absolute class names to a
        list of their base class names.

        :arg derived_classes: Dictionary mapping absolute class names to
        a list of the class names that derive from them.

        :arg names: Dictionary mapping local names to the actual name
        they point to. For example, if you have `from os import path`
        in a module called `foo.bar`, then the key `foo.bar.path` would
        map to `os.path`.

        """
        super(FileToIndex, self).__init__(path, contents, plugin_name, tree)

        self.python_path = python_path
        self.class_bases = class_bases
        self.derived_classes = derived_classes
        self.names = names

        self.module_name = path_to_module(self.python_path, self.path)

    def is_interesting(self):
        return is_interesting(self.path)

    def needles_by_line(self):
        self.node_start_table = self.analyze_tokens()

        visitor = IndexingNodeVisitor(self)
        syntax_tree = ast.parse(self.contents)

        return iterable_per_line(
            with_start_and_end(
                split_into_lines(
                    visitor.get_needles(syntax_tree)
                )
            )
        )

    def analyze_tokens(self):
        """Split the file into tokens and analyze them for data needed
        for indexing.

        """
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

        return node_start_table

    def get_node_start_end(self, node):
        """Return start and end positions within the file for the given
        AST Node.

        """
        start = node.lineno, node.col_offset
        if start in self.node_start_table:
            start = self.node_start_table[start]

        end = None
        if isinstance(node, ast.ClassDef) or isinstance(node, ast.FunctionDef):
            end = start[0], start[1] + len(node.name)
        elif isinstance(node, ast.Call):
            name = convert_node_to_name(node.func)
            if name:
                end = start[0], start[1] + len(name)

        return start, end

    def get_bases_for_class(self, absolute_class_name):
        """Return a list of all the classes that the given class
        inherits from in their canonical form.

        """
        for base in self.class_bases[absolute_class_name]:
            base = normalize_name(self.names, base)
            yield base
            for base_parent in self.get_bases_for_class(base):
                yield base_parent

    def get_derived_for_class(self, absolute_class_name):
        """Return a list of all the classes that derive from the given
        class in their canonical form.

        """
        for derived in self.derived_classes[absolute_class_name]:
            yield derived
            for derived_child in self.get_derived_for_class(derived):
                yield derived_child


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


def package_for_module(module_path):
    return module_path.rsplit('.', 1)[0] if '.' in module_path else None


def convert_node_to_name(node):
    """Convert an AST node to a name if possible. Return None if we
    can't (such as function calls).

    """
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        value_name = convert_node_to_name(node.value)
        if value_name:
            return value_name + '.' + node.attr
    else:
        return None


def normalize_name(names, absolute_local_name):
    """Given a local name, figure out the actual module that the
    thing that name points to lives and return that name.

    For example, if you have `from os import path` in a module
    called `foo.bar`, then the name `foo.bar.path` would return
    `os.path`.

    """
    while absolute_local_name in names:
        absolute_local_name = names[absolute_local_name]

    # For cases when you `import foo.bar` and refer to `foo.bar.baz`, we
    # need to normalize the `foo.bar` prefix in case it's not the
    # canonical name of that module.
    if '.' in absolute_local_name:
        prefix, local_name = absolute_local_name.rsplit('.', 1)
        return normalize_name(names, prefix) + '.' + local_name
    else:
        return absolute_local_name


def is_interesting(path):
    """Determine if the file at the given path is interesting enough to
    analyze.

    """
    return path.endswith('.py')


def path_to_module(python_path, module_path):
    """Convert a file path into a dotted module path, using the given
    python_path as the base directory that modules live in.

    """
    module_path = trim_end(module_path, '.py')
    module_path = trim_end(module_path, '/__init__')
    common_path = os.path.commonprefix([python_path, module_path])
    return module_path.replace(common_path, '', 1).replace('/', '.').strip('.')


def trim_end(string, end):
    if string.endswith(end):
        return string[:-len(end)]
    else:
        return string
